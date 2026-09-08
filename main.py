import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="Laundry Loyverse API",
    version="1.0.0",
)

LOYVERSE_API_URL = "https://api.loyverse.com/v1.0"
STORE_TIMEZONE = ZoneInfo("America/Guatemala")


def get_headers():
    token = os.getenv("LOYVERSE_TOKEN")

    if not token:
        raise HTTPException(
            status_code=500,
            detail="LOYVERSE_TOKEN is not configured",
        )

    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def convert_date_range(from_date: date, to_date: date):
    if from_date > to_date:
        raise HTTPException(
            status_code=400,
            detail="from_date cannot be later than to_date",
        )

    local_start = datetime.combine(
        from_date,
        time.min,
        tzinfo=STORE_TIMEZONE,
    )

    local_end = datetime.combine(
        to_date + timedelta(days=1),
        time.min,
        tzinfo=STORE_TIMEZONE,
    )

return (
    local_start.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    ),
    local_end.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z"
    ),
)


async def fetch_all(endpoint: str, collection_name: str, params=None):
    results = []
    request_params = dict(params or {})
    request_params["limit"] = 250

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            response = await client.get(
                f"{LOYVERSE_API_URL}/{endpoint}",
                headers=get_headers(),
                params=request_params,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail={
                        "message": "Loyverse request failed",
                        "response": response.text,
                    },
                )

            data = response.json()
            results.extend(data.get(collection_name, []))

            cursor = data.get("cursor")
            if not cursor:
                break

            request_params["cursor"] = cursor

    return results


@app.get("/")
async def root():
    return {
        "status": "online",
        "business": "Laundry",
        "timezone": "America/Guatemala",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/items")
async def items():
    records = await fetch_all("items", "items")

    return {
        "count": len(records),
        "items": records,
    }


@app.get("/receipts")
async def receipts(
    from_date: date = Query(..., description="YYYY-MM-DD"),
    to_date: date = Query(..., description="YYYY-MM-DD"),
):
    created_at_min, created_at_max = convert_date_range(
        from_date,
        to_date,
    )

    records = await fetch_all(
        "receipts",
        "receipts",
        {
            "created_at_min": created_at_min,
            "created_at_max": created_at_max,
        },
    )

    return {
        "count": len(records),
        "filters": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
        "receipts": records,
    }


@app.get("/modifiers")
async def modifiers():
    records = await fetch_all("modifiers", "modifiers")

    return {
        "count": len(records),
        "modifiers": records,
    }