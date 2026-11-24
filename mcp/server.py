import os
import math
import pyotp
import pandas as pd
from typing import Any, Literal, Optional
from dotenv import load_dotenv
from growwapi import GrowwAPI, GrowwFeed
from mcp.server import MCPServer

load_dotenv()

mcp = MCPServer("Groww Trading Server",debug=True)

_groww_client: Optional[GrowwAPI] = None
_feed_client: Optional[GrowwFeed] = None


# =====================================================================
# AUTHENTICATION & CLIENT MANAGEMENT
# =====================================================================

def get_groww_client(force_refresh: bool = False) -> GrowwAPI:
    """
    Initialize and cache the GrowwAPI client using one of the supported auth flows:
    1. Direct access token via `access_token` (or `GROWW_ACCESS_TOKEN`) in .env
    2. TOTP flow via `api_key` + `totp_secret` in .env (non-expiring TOTP key)
    3. API Key & Secret flow via `api_key` + `secret` in .env (requires daily approval)
    """
    global _groww_client, _feed_client
    if _groww_client is not None and not force_refresh:
        return _groww_client

    api_key = os.getenv("api_key") or os.getenv("GROWW_API_KEY")
    secret = os.getenv("secret") or os.getenv("GROWW_API_SECRET")
    totp_gen = pyotp.TOTP(secret)
    totp = totp_gen.now()

    
    if api_key and totp:
        access_token = GrowwAPI.get_access_token(api_key=api_key, totp=totp)
    #elif api_key and secret:
    #    access_token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
    else:
        raise ValueError(
            "Missing Groww credentials in .env. Provide either `access_token`, "
            "`api_key` + `totp_secret`, or `api_key` + `secret`."
        )

    _groww_client = GrowwAPI(access_token)
    _feed_client = None
    return _groww_client


def get_feed_client() -> GrowwFeed:
    """Return a persistent GrowwFeed WebSocket client tied to the active GrowwAPI session."""
    global _feed_client
    groww = get_groww_client()
    if _feed_client is None:
        _feed_client = GrowwFeed(groww)
    return _feed_client


@mcp.tool()
def refresh_groww_session() -> dict:
    """Re-authenticate with Groww API and refresh the cached access token and feed client."""
    get_groww_client(force_refresh=True)
    return {"status": "authenticated", "message": "GrowwAPI session refreshed successfully."}


# =====================================================================
# SDK CONSTANT MAPPERS & SERIALIZATION HELPERS (ANNEXURES)
# =====================================================================

def _clean_nans(data: dict) -> dict:
    """Replace float NaN values returned by Groww SDK instrument dicts with None for JSON safety."""
    return {
        k: (None if isinstance(v, float) and math.isnan(v) else v)
        for k, v in data.items()
    }


def _map_exchange(groww: GrowwAPI, exchange: str) -> str:
    mapping = {
        "NSE": groww.EXCHANGE_NSE,
        "BSE": groww.EXCHANGE_BSE,
    }
    return mapping[exchange.upper()]


def _map_segment(groww: GrowwAPI, segment: str) -> str:
    mapping = {
        "CASH": groww.SEGMENT_CASH,
        "FNO": groww.SEGMENT_FNO,
    }
    return mapping[segment.upper()]


def _map_order_type(groww: GrowwAPI, order_type: str) -> str:
    mapping = {
        "LIMIT": groww.ORDER_TYPE_LIMIT,
        "MARKET": groww.ORDER_TYPE_MARKET,
        "SL": groww.ORDER_TYPE_STOP_LOSS,
        "STOP_LOSS": groww.ORDER_TYPE_STOP_LOSS,
        "SL_M": groww.ORDER_TYPE_STOP_LOSS_MARKET,
        "STOP_LOSS_MARKET": groww.ORDER_TYPE_STOP_LOSS_MARKET,
    }
    return mapping[order_type.upper()]


def _map_product(groww: GrowwAPI, product: str) -> str:
    mapping = {
        "CNC": groww.PRODUCT_CNC,
        "MIS": groww.PRODUCT_MIS,
        "NRML": groww.PRODUCT_NRML,
    }
    return mapping[product.upper()]


def _map_transaction_type(groww: GrowwAPI, transaction_type: str) -> str:
    mapping = {
        "BUY": groww.TRANSACTION_TYPE_BUY,
        "SELL": groww.TRANSACTION_TYPE_SELL,
    }
    return mapping[transaction_type.upper()]


def _map_validity(groww: GrowwAPI, validity: str) -> str:
    mapping = {
        "DAY": groww.VALIDITY_DAY,
    }
    return mapping.get(validity.upper(), groww.VALIDITY_DAY)


def _map_trigger_direction(groww: GrowwAPI, direction: str) -> str:
    mapping = {
        "UP": groww.TRIGGER_DIRECTION_UP,
        "DOWN": groww.TRIGGER_DIRECTION_DOWN,
    }
    return mapping[direction.upper()]


def _map_smart_order_type(groww: GrowwAPI, smart_order_type: str) -> str:
    mapping = {
        "GTT": groww.SMART_ORDER_TYPE_GTT,
        "OCO": groww.SMART_ORDER_TYPE_OCO,
    }
    return mapping[smart_order_type.upper()]


def _map_smart_order_status(groww: GrowwAPI, status: str) -> str:
    mapping = {
        "ACTIVE": groww.SMART_ORDER_STATUS_ACTIVE,
        "TRIGGERED": groww.SMART_ORDER_STATUS_TRIGGERED,
        "CANCELLED": groww.SMART_ORDER_STATUS_CANCELLED,
        "EXPIRED": groww.SMART_ORDER_STATUS_EXPIRED,
        "FAILED": groww.SMART_ORDER_STATUS_FAILED,
        "COMPLETED": groww.SMART_ORDER_STATUS_COMPLETED,
    }
    return mapping[status.upper()]


def _map_candle_interval(groww: GrowwAPI, interval: str) -> str:
    mapping = {
        "1minute": groww.CANDLE_INTERVAL_MIN_1,
        "2minute": groww.CANDLE_INTERVAL_MIN_2,
        "3minute": groww.CANDLE_INTERVAL_MIN_3,
        "5minute": groww.CANDLE_INTERVAL_MIN_5,
        "10minute": groww.CANDLE_INTERVAL_MIN_10,
        "15minute": groww.CANDLE_INTERVAL_MIN_15,
        "30minute": groww.CANDLE_INTERVAL_MIN_30,
        "1hour": groww.CANDLE_INTERVAL_HOUR_1,
        "4hour": groww.CANDLE_INTERVAL_HOUR_4,
        "1day": groww.CANDLE_INTERVAL_DAY,
        "1week": groww.CANDLE_INTERVAL_WEEK,
        "1month": groww.CANDLE_INTERVAL_MONTH,
    }
    return mapping[interval]


# =====================================================================
# 1. INSTRUMENTS
# =====================================================================

@mcp.tool()
def get_instrument_by_symbol(groww_symbol: str) -> dict:
    """
    Fetch instrument details using its Groww symbol
    (e.g., 'NSE-RELIANCE', 'NSE-NIFTY-30Sep25-FUT', 'NSE-NIFTY-30Sep25-24650-CE').
    """
    groww = get_groww_client()
    res = groww.get_instrument_by_groww_symbol(groww_symbol=groww_symbol)
    return _clean_nans(res)


@mcp.tool()
def get_instrument_by_trading_symbol_and_exchange(
    exchange: Literal["NSE", "BSE"],
    trading_symbol: str,
) -> dict:
    """Fetch instrument details for a given exchange ('NSE' or 'BSE') and trading symbol (e.g., 'RELIANCE')."""
    groww = get_groww_client()
    res = groww.get_instrument_by_exchange_and_trading_symbol(
        exchange=_map_exchange(groww, exchange),
        trading_symbol=trading_symbol.upper(),
    )
    return _clean_nans(res)


@mcp.tool()
def get_instrument_by_exchange_token(exchange_token: str) -> dict:
    """Fetch instrument details using its unique exchange token (e.g., '2885')."""
    groww = get_groww_client()
    res = groww.get_instrument_by_exchange_token(exchange_token=str(exchange_token))
    return _clean_nans(res)


@mcp.tool()
def get_all_instruments(
    search: Optional[str] = None,
    exchange: Optional[Literal["NSE", "BSE"]] = None,
    segment: Optional[Literal["CASH", "FNO"]] = None,
    instrument_type: Optional[Literal["EQ", "IDX", "FUT", "CE", "PE"]] = None,
    underlying_symbol: Optional[str] = None,
    expiry_date: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """
    Fetch tradable instruments from groww.get_all_instruments() with optional filtering by
    search query (trading_symbol, groww_symbol, name, isin), exchange, segment, instrument_type,
    underlying_symbol, or expiry_date (YYYY-MM-DD).
    """
    groww = get_groww_client()
    df = groww.get_all_instruments()

    if exchange:
        df = df[df["exchange"] == exchange.upper()]
    if segment:
        df = df[df["segment"] == segment.upper()]
    if instrument_type:
        df = df[df["instrument_type"] == instrument_type.upper()]
    if underlying_symbol:
        df = df[df["underlying_symbol"].astype(str).str.upper() == underlying_symbol.upper()]
    if expiry_date:
        df = df[df["expiry_date"].astype(str) == expiry_date]
    if search:
        q = search.upper()
        mask = (
            df["trading_symbol"].astype(str).str.upper().str.contains(q, na=False)
            | df["groww_symbol"].astype(str).str.upper().str.contains(q, na=False)
            | df["name"].astype(str).str.upper().str.contains(q, na=False)
            | df["isin"].astype(str).str.upper().str.contains(q, na=False)
        )
        df = df[mask]

    df = df.head(limit).where(pd.notnull(df), None)
    return df.to_dict(orient="records")


@mcp.tool()
def get_instrument_csv_url() -> str:
    """Return the direct URL (groww.INSTRUMENT_CSV_URL) to download the full Groww instruments CSV."""
    groww = get_groww_client()
    return groww.INSTRUMENT_CSV_URL


@mcp.tool()
def load_raw_instruments(limit: int = 50) -> list[dict]:
    """Load instruments via the SDK's internal CSV loader groww._load_instruments()."""
    groww = get_groww_client()
    df = groww._load_instruments()
    df = df.head(limit).where(pd.notnull(df), None)
    return df.to_dict(orient="records")


# =====================================================================
# 2. ORDERS
# =====================================================================

@mcp.tool()
def place_order(
    trading_symbol: str,
    quantity: int,
    exchange: Literal["NSE", "BSE"],
    segment: Literal["CASH", "FNO"],
    product: Literal["CNC", "MIS", "NRML"],
    order_type: Literal["LIMIT", "MARKET", "SL", "SL_M"],
    transaction_type: Literal["BUY", "SELL"],
    validity: Literal["DAY"] = "DAY",
    price: Optional[float] = None,
    trigger_price: Optional[float] = None,
    order_reference_id: Optional[str] = None,
) -> dict:
    """
    Place a new equity (CASH) or derivatives (FNO) order.
    - price: Required for LIMIT and SL orders.
    - trigger_price: Required for SL and SL_M orders.
    - order_reference_id: Optional 8-20 char alphanumeric string (max 2 hyphens) to track the order.
    """
    groww = get_groww_client()
    kwargs: dict[str, Any] = {
        "trading_symbol": trading_symbol.upper(),
        "quantity": quantity,
        "validity": _map_validity(groww, validity),
        "exchange": _map_exchange(groww, exchange),
        "segment": _map_segment(groww, segment),
        "product": _map_product(groww, product),
        "order_type": _map_order_type(groww, order_type),
        "transaction_type": _map_transaction_type(groww, transaction_type),
    }
    if price is not None:
        kwargs["price"] = price
    if trigger_price is not None:
        kwargs["trigger_price"] = trigger_price
    if order_reference_id is not None:
        kwargs["order_reference_id"] = order_reference_id

    return groww.place_order(**kwargs)


@mcp.tool()
def modify_order(
    groww_order_id: str,
    segment: Literal["CASH", "FNO"],
    order_type: Literal["LIMIT", "MARKET", "SL", "SL_M"],
    quantity: int,
    price: Optional[float] = None,
    trigger_price: Optional[float] = None,
) -> dict:
    """Modify an existing pending or open order."""
    groww = get_groww_client()
    kwargs: dict[str, Any] = {
        "groww_order_id": groww_order_id,
        "segment": _map_segment(groww, segment),
        "order_type": _map_order_type(groww, order_type),
        "quantity": quantity,
    }
    if price is not None:
        kwargs["price"] = price
    if trigger_price is not None:
        kwargs["trigger_price"] = trigger_price

    return groww.modify_order(**kwargs)


@mcp.tool()
def cancel_order(
    groww_order_id: str,
    segment: Literal["CASH", "FNO"],
) -> dict:
    """Cancel a pending or open order by its Groww order ID."""
    groww = get_groww_client()
    return groww.cancel_order(
        segment=_map_segment(groww, segment),
        groww_order_id=groww_order_id,
    )


@mcp.tool()
def get_trade_list_for_order(
    groww_order_id: str,
    segment: Literal["CASH", "FNO"],
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """Retrieve executed trades for a specific Groww order ID (max page_size is 50)."""
    groww = get_groww_client()
    return groww.get_trade_list_for_order(
        groww_order_id=groww_order_id,
        segment=_map_segment(groww, segment),
        page=page,
        page_size=min(page_size, 50),
    )


@mcp.tool()
def get_order_status(
    groww_order_id: str,
    segment: Literal["CASH", "FNO"],
) -> dict:
    """Check the current status and filled quantity of an order by its Groww order ID."""
    groww = get_groww_client()
    return groww.get_order_status(
        groww_order_id=groww_order_id,
        segment=_map_segment(groww, segment),
    )


@mcp.tool()
def get_order_status_by_reference(
    order_reference_id: str,
    segment: Literal["CASH", "FNO"],
) -> dict:
    """Check order status using the user-provided order_reference_id."""
    groww = get_groww_client()
    return groww.get_order_status_by_reference(
        order_reference_id=order_reference_id,
        segment=_map_segment(groww, segment),
    )


@mcp.tool()
def get_order_list(
    segment: Optional[Literal["CASH", "FNO"]] = None,
    page: int = 0,
    page_size: int = 100,
) -> dict:
    """
    Retrieve all orders placed today (open, pending, or executed).
    If segment is omitted, returns orders across both CASH and FNO segments.
    """
    groww = get_groww_client()
    kwargs: dict[str, Any] = {
        "page": page,
        "page_size": page_size,
    }
    if segment:
        kwargs["segment"] = _map_segment(groww, segment)
    return groww.get_order_list(**kwargs)


@mcp.tool()
def get_order_detail(
    groww_order_id: str,
    segment: Literal["CASH", "FNO"],
) -> dict:
    """Fetch complete details for a specific order ID."""
    groww = get_groww_client()
    return groww.get_order_detail(
        groww_order_id=groww_order_id,
        segment=_map_segment(groww, segment),
    )


# =====================================================================
# 3. SMART ORDERS (GTT & OCO)
# =====================================================================

@mcp.tool()
def create_gtt_smart_order(
    reference_id: str,
    segment: Literal["CASH", "FNO"],
    trading_symbol: str,
    quantity: int,
    product_type: Literal["CNC", "MIS", "NRML"],
    exchange: Literal["NSE", "BSE"],
    trigger_price: str,
    trigger_direction: Literal["UP", "DOWN"],
    order_type: Literal["LIMIT", "MARKET", "SL", "SL_M"],
    transaction_type: Literal["BUY", "SELL"],
    order_price: Optional[str] = None,
    duration: Literal["DAY"] = "DAY",
    child_legs: Optional[dict] = None,
) -> dict:
    """
    Create a Good-Till-Triggered (GTT) smart order (valid for 1 year by default).
    - reference_id: 8-20 char alphanumeric idempotency key (max 2 hyphens).
    - trigger_price & order_price: Decimal strings (e.g., '3985.00').
    - order_price: Required if order_type is LIMIT or SL.
    """
    groww = get_groww_client()
    order_payload: dict[str, Any] = {
        "order_type": _map_order_type(groww, order_type),
        "transaction_type": _map_transaction_type(groww, transaction_type),
    }
    if order_price is not None:
        order_payload["price"] = str(order_price)

    kwargs: dict[str, Any] = {
        "smart_order_type": groww.SMART_ORDER_TYPE_GTT,
        "reference_id": reference_id,
        "segment": _map_segment(groww, segment),
        "trading_symbol": trading_symbol.upper(),
        "quantity": quantity,
        "product_type": _map_product(groww, product_type),
        "exchange": _map_exchange(groww, exchange),
        "duration": _map_validity(groww, duration),
        "trigger_price": str(trigger_price),
        "trigger_direction": _map_trigger_direction(groww, trigger_direction),
        "order": order_payload,
    }
    if child_legs is not None:
        kwargs["child_legs"] = child_legs

    return groww.create_smart_order(**kwargs)


@mcp.tool()
def create_oco_smart_order(
    reference_id: str,
    segment: Literal["CASH", "FNO"],
    trading_symbol: str,
    quantity: int,
    net_position_quantity: int,
    transaction_type: Literal["BUY", "SELL"],
    product_type: Literal["MIS", "NRML"],
    exchange: Literal["NSE", "BSE"],
    target_trigger_price: str,
    target_order_type: Literal["LIMIT", "MARKET"],
    stop_loss_trigger_price: str,
    stop_loss_order_type: Literal["SL", "SL_M"],
    target_price: Optional[str] = None,
    stop_loss_price: Optional[str] = None,
    duration: Literal["DAY"] = "DAY",
) -> dict:
    """
    Create a One-Cancels-Other (OCO) smart order (target + stop-loss) to protect/exit an existing position.
    - Note: For CASH segment, use product_type='MIS'; for FNO segment, use product_type='NRML'.
    - quantity must be <= abs(net_position_quantity).
    - All prices must be decimal strings (e.g., '120.50').
    """
    groww = get_groww_client()
    target_leg = {
        "trigger_price": str(target_trigger_price),
        "order_type": _map_order_type(groww, target_order_type),
        "price": str(target_price) if target_price is not None else None,
    }
    stop_loss_leg = {
        "trigger_price": str(stop_loss_trigger_price),
        "order_type": _map_order_type(groww, stop_loss_order_type),
        "price": str(stop_loss_price) if stop_loss_price is not None else None,
    }
    return groww.create_smart_order(
        smart_order_type=groww.SMART_ORDER_TYPE_OCO,
        reference_id=reference_id,
        segment=_map_segment(groww, segment),
        trading_symbol=trading_symbol.upper(),
        quantity=quantity,
        product_type=_map_product(groww, product_type),
        exchange=_map_exchange(groww, exchange),
        duration=_map_validity(groww, duration),
        net_position_quantity=net_position_quantity,
        transaction_type=_map_transaction_type(groww, transaction_type),
        target=target_leg,
        stop_loss=stop_loss_leg,
    )


@mcp.tool()
def modify_gtt_smart_order(
    smart_order_id: str,
    segment: Literal["CASH", "FNO"],
    quantity: int,
    trigger_price: str,
    trigger_direction: Literal["UP", "DOWN"],
    order_type: Literal["LIMIT", "MARKET", "SL", "SL_M"],
    transaction_type: Literal["BUY", "SELL"],
    order_price: Optional[str] = None,
    child_legs: Optional[dict] = None,
) -> dict:
    """
    Modify an existing GTT smart order.
    Note: transaction_type is required for routing/validation but is not modifiable.
    """
    groww = get_groww_client()
    order_payload: dict[str, Any] = {
        "order_type": _map_order_type(groww, order_type),
        "price": str(order_price) if order_price is not None else None,
        "transaction_type": _map_transaction_type(groww, transaction_type),
    }
    kwargs: dict[str, Any] = {
        "smart_order_id": smart_order_id,
        "smart_order_type": groww.SMART_ORDER_TYPE_GTT,
        "segment": _map_segment(groww, segment),
        "quantity": quantity,
        "trigger_price": str(trigger_price),
        "trigger_direction": _map_trigger_direction(groww, trigger_direction),
        "order": order_payload,
    }
    if child_legs is not None:
        kwargs["child_legs"] = child_legs

    return groww.modify_smart_order(**kwargs)


@mcp.tool()
def modify_oco_smart_order(
    smart_order_id: str,
    segment: Literal["CASH", "FNO"],
    quantity: int,
    product_type: Literal["MIS", "NRML"],
    target_trigger_price: str,
    stop_loss_trigger_price: str,
    duration: Literal["DAY"] = "DAY",
) -> dict:
    """
    Modify an existing OCO smart order (modifiable fields: quantity, duration, product_type,
    target.trigger_price, and stop_loss.trigger_price).
    """
    groww = get_groww_client()
    return groww.modify_smart_order(
        smart_order_id=smart_order_id,
        smart_order_type=groww.SMART_ORDER_TYPE_OCO,
        segment=_map_segment(groww, segment),
        quantity=quantity,
        duration=_map_validity(groww, duration),
        product_type=_map_product(groww, product_type),
        target={"trigger_price": str(target_trigger_price)},
        stop_loss={"trigger_price": str(stop_loss_trigger_price)},
    )


@mcp.tool()
def cancel_smart_order(
    segment: Literal["CASH", "FNO"],
    smart_order_type: Literal["GTT", "OCO"],
    smart_order_id: str,
) -> dict:
    """Cancel an active GTT or OCO smart order."""
    groww = get_groww_client()
    return groww.cancel_smart_order(
        segment=_map_segment(groww, segment),
        smart_order_type=_map_smart_order_type(groww, smart_order_type),
        smart_order_id=smart_order_id,
    )


@mcp.tool()
def get_smart_order(
    segment: Literal["CASH", "FNO"],
    smart_order_type: Literal["GTT", "OCO"],
    smart_order_id: str,
) -> dict:
    """Retrieve details of a specific GTT or OCO smart order by ID."""
    groww = get_groww_client()
    return groww.get_smart_order(
        segment=_map_segment(groww, segment),
        smart_order_type=_map_smart_order_type(groww, smart_order_type),
        smart_order_id=smart_order_id,
    )


@mcp.tool()
def get_smart_order_list(
    segment: Optional[Literal["CASH", "FNO"]] = None,
    smart_order_type: Optional[Literal["GTT", "OCO"]] = None,
    status: Optional[
        Literal["ACTIVE", "TRIGGERED", "CANCELLED", "EXPIRED", "FAILED", "COMPLETED"]
    ] = None,
    page: int = 0,
    page_size: int = 20,
    start_date_time: Optional[str] = None,
    end_date_time: Optional[str] = None,
) -> dict:
    """
    Filter and list smart orders by segment, type, status, and ISO-8601 time window
    (e.g., '2025-01-16T09:15:00'). Date window must not exceed 1 month.
    """
    groww = get_groww_client()
    kwargs: dict[str, Any] = {
        "page": page,
        "page_size": min(max(page_size, 1), 50),
    }
    if segment:
        kwargs["segment"] = _map_segment(groww, segment)
    if smart_order_type:
        kwargs["smart_order_type"] = _map_smart_order_type(groww, smart_order_type)
    if status:
        kwargs["status"] = _map_smart_order_status(groww, status)
    if start_date_time:
        kwargs["start_date_time"] = start_date_time
    if end_date_time:
        kwargs["end_date_time"] = end_date_time

    return groww.get_smart_order_list(**kwargs)


# =====================================================================
# 4. PORTFOLIO
# =====================================================================

@mcp.tool()
def get_holdings(timeout: int = 5) -> dict:
    """Fetch all current long-term DEMAT equity holdings in the user's Groww account."""
    groww = get_groww_client()
    return groww.get_holdings_for_user(timeout=timeout)


@mcp.tool()
def get_positions(segment: Optional[Literal["CASH", "FNO"]] = None) -> dict:
    """
    Fetch open trading positions for the user.
    If segment is omitted, fetches positions across both CASH and FNO segments.
    """
    groww = get_groww_client()
    if segment:
        return groww.get_positions_for_user(segment=_map_segment(groww, segment))
    return groww.get_positions_for_user()


@mcp.tool()
def get_position_for_trading_symbol(
    trading_symbol: str,
    segment: Literal["CASH", "FNO"],
) -> dict:
    """Retrieve detailed position information for a specific trading symbol and segment."""
    groww = get_groww_client()
    return groww.get_position_for_trading_symbol(
        trading_symbol=trading_symbol.upper(),
        segment=_map_segment(groww, segment),
    )


# =====================================================================
# 5. MARGIN
# =====================================================================

@mcp.tool()
def get_available_margin_details() -> dict:
    """Retrieve available margin details for equity (CNC/MIS) and F&O (SPAN/Exposure/Option) segments."""
    groww = get_groww_client()
    return groww.get_available_margin_details()


@mcp.tool()
def get_order_margin_details(
    segment: Literal["CASH", "FNO"],
    orders: list[dict],
) -> dict:
    """
    Calculate required margin and charges for a single order or a basket of F&O orders.
    Each item in `orders` should contain:
    - trading_symbol (str), transaction_type ('BUY'|'SELL'), quantity (int),
      order_type ('LIMIT'|'MARKET'|'SL'|'SL_M'), product ('CNC'|'MIS'|'NRML'),
      exchange ('NSE'|'BSE'), and optional price (float).
    """
    groww = get_groww_client()
    normalized_orders = []
    for o in orders:
        item: dict[str, Any] = {
            "trading_symbol": str(o["trading_symbol"]).upper(),
            "transaction_type": _map_transaction_type(groww, o["transaction_type"]),
            "quantity": int(o["quantity"]),
            "order_type": _map_order_type(groww, o["order_type"]),
            "product": _map_product(groww, o["product"]),
            "exchange": _map_exchange(groww, o["exchange"]),
        }
        if "price" in o and o["price"] is not None:
            item["price"] = float(o["price"])
        normalized_orders.append(item)

    return groww.get_order_margin_details(
        orders=normalized_orders,
        segment=_map_segment(groww, segment),
    )


# =====================================================================
# 6. LIVE DATA
# =====================================================================

@mcp.tool()
def get_quote(
    exchange: Literal["NSE", "BSE"],
    segment: Literal["CASH", "FNO"],
    trading_symbol: str,
) -> dict:
    """Fetch full real-time market quote (LTP, OHLC, depth, OI, volume, 52-week high/low) for an instrument."""
    groww = get_groww_client()
    return groww.get_quote(
        exchange=_map_exchange(groww, exchange),
        segment=_map_segment(groww, segment),
        trading_symbol=trading_symbol.upper(),
    )


@mcp.tool()
def get_ltp(
    segment: Literal["CASH", "FNO"],
    exchange_trading_symbols: list[str],
) -> dict:
    """
    Fetch Last Traded Price (LTP) for up to 50 instruments at once.
    Format symbols as 'EXCHANGE_TRADINGSYMBOL' (e.g., ['NSE_NIFTY', 'NSE_RELIANCE']).
    """
    groww = get_groww_client()
    symbols = tuple(s.upper() for s in exchange_trading_symbols[:50])
    return groww.get_ltp(
        segment=_map_segment(groww, segment),
        exchange_trading_symbols=symbols,
    )


@mcp.tool()
def get_ohlc(
    segment: Literal["CASH", "FNO"],
    exchange_trading_symbols: list[str],
) -> dict:
    """
    Fetch real-time snapshot OHLC (Open, High, Low, Close) for up to 50 instruments at once.
    Format symbols as 'EXCHANGE_TRADINGSYMBOL' (e.g., ['NSE_NIFTY', 'NSE_RELIANCE']).
    """
    groww = get_groww_client()
    symbols = tuple(s.upper() for s in exchange_trading_symbols[:50])
    return groww.get_ohlc(
        segment=_map_segment(groww, segment),
        exchange_trading_symbols=symbols,
    )


@mcp.tool()
def get_option_chain(
    exchange: Literal["NSE", "BSE"],
    underlying: str,
    expiry_date: str,
) -> dict:
    """
    Fetch complete option chain (CE & PE strikes with LTP, OI, volume, IV, and Greeks)
    for an underlying symbol (e.g., 'NIFTY', 'BANKNIFTY', 'RELIANCE') and expiry_date ('YYYY-MM-DD').
    """
    groww = get_groww_client()
    return groww.get_option_chain(
        exchange=_map_exchange(groww, exchange),
        underlying=underlying.upper(),
        expiry_date=expiry_date,
    )


@mcp.tool()
def get_greeks(
    exchange: Literal["NSE", "BSE"],
    underlying: str,
    trading_symbol: str,
    expiry: str,
) -> dict:
    """
    Fetch option Greeks (delta, gamma, theta, vega, rho, iv) for a specific F&O option contract.
    - expiry: Contract expiry date in 'YYYY-MM-DD' format.
    """
    groww = get_groww_client()
    return groww.get_greeks(
        exchange=_map_exchange(groww, exchange),
        underlying=underlying.upper(),
        trading_symbol=trading_symbol.upper(),
        expiry=expiry,
    )


# =====================================================================
# 7. HISTORICAL DATA & BACKTESTING
# =====================================================================

@mcp.tool()
def get_expiries(
    exchange: Literal["NSE", "BSE"],
    underlying_symbol: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
) -> dict:
    """
    Retrieve available F&O expiry dates (YYYY-MM-DD) for an exchange and underlying symbol (from 2020 onward).
    """
    groww = get_groww_client()
    kwargs: dict[str, Any] = {
        "exchange": _map_exchange(groww, exchange),
        "underlying_symbol": underlying_symbol.upper(),
    }
    if year is not None:
        kwargs["year"] = year
    if month is not None:
        kwargs["month"] = month
    return groww.get_expiries(**kwargs)


@mcp.tool()
def get_contracts(
    exchange: Literal["NSE", "BSE"],
    underlying_symbol: str,
    expiry_date: str,
) -> dict:
    """
    Retrieve available F&O contract Groww symbols for a given exchange, underlying_symbol,
    and expiry_date ('YYYY-MM-DD').
    """
    groww = get_groww_client()
    return groww.get_contracts(
        exchange=_map_exchange(groww, exchange),
        underlying_symbol=underlying_symbol.upper(),
        expiry_date=expiry_date,
    )


@mcp.tool()
def get_historical_candles(
    exchange: Literal["NSE", "BSE"],
    segment: Literal["CASH", "FNO"],
    groww_symbol: str,
    start_time: str,
    end_time: str,
    candle_interval: Literal[
        "1minute",
        "2minute",
        "3minute",
        "5minute",
        "10minute",
        "15minute",
        "30minute",
        "1hour",
        "4hour",
        "1day",
        "1week",
        "1month",
    ] = "5minute",
) -> dict:
    """
    Fetch historical OHLCV (+ OI for FNO) candles for backtesting (data available from 2020).
    - groww_symbol: e.g., 'NSE-WIPRO', 'NSE-NIFTY-30Sep25-FUT'
    - start_time & end_time: 'yyyy-MM-dd HH:mm:ss' or epoch seconds string.
    """
    groww = get_groww_client()
    return groww.get_historical_candles(
        exchange=_map_exchange(groww, exchange),
        segment=_map_segment(groww, segment),
        groww_symbol=groww_symbol,
        start_time=start_time,
        end_time=end_time,
        candle_interval=_map_candle_interval(groww, candle_interval),
    )


@mcp.tool()
def get_historical_candle_data_legacy(
    exchange: Literal["NSE", "BSE"],
    segment: Literal["CASH", "FNO"],
    trading_symbol: str,
    start_time: str,
    end_time: str,
    interval_in_minutes: int = 5,
) -> dict:
    """
    [Legacy/Deprecated in SDK - prefer get_historical_candles]
    Fetch historical candle data using trading_symbol and interval_in_minutes (1, 5, 10, 60, 240, 1440, 10080).
    - start_time & end_time: 'YYYY-MM-DD HH:mm:ss' or epoch milliseconds string.
    """
    groww = get_groww_client()
    return groww.get_historical_candle_data(
        trading_symbol=trading_symbol.upper(),
        exchange=_map_exchange(groww, exchange),
        segment=_map_segment(groww, segment),
        start_time=start_time,
        end_time=end_time,
        interval_in_minutes=interval_in_minutes,
    )


# =====================================================================
# 8. FEED (WEBSOCKET STREAMING & POLLING)
# =====================================================================

@mcp.tool()
def feed_subscribe_ltp(instruments_list: list[dict]) -> dict:
    """
    Subscribe to live LTP WebSocket stream for up to 1000 equity/FNO instruments.
    Each item in `instruments_list`: {"exchange": "NSE", "segment": "CASH", "exchange_token": "2885"}.
    """
    feed = get_feed_client()
    feed.subscribe_ltp(instruments_list)
    return {"status": "subscribed", "feed": "ltp", "count": len(instruments_list)}


@mcp.tool()
def feed_get_ltp() -> dict:
    """Poll the latest received LTP values from active GrowwFeed LTP subscriptions."""
    feed = get_feed_client()
    return feed.get_ltp()


@mcp.tool()
def feed_unsubscribe_ltp(instruments_list: list[dict]) -> dict:
    """Unsubscribe from live LTP WebSocket stream for the given instruments."""
    feed = get_feed_client()
    feed.unsubscribe_ltp(instruments_list)
    return {"status": "unsubscribed", "feed": "ltp", "count": len(instruments_list)}


@mcp.tool()
def feed_subscribe_index_value(instruments_list: list[dict]) -> dict:
    """
    Subscribe to live index values (e.g., [{"exchange": "NSE", "segment": "CASH", "exchange_token": "NIFTY"}]).
    """
    feed = get_feed_client()
    feed.subscribe_index_value(instruments_list)
    return {"status": "subscribed", "feed": "index_value", "count": len(instruments_list)}


@mcp.tool()
def feed_get_index_value() -> dict:
    """Poll the latest received index values from active GrowwFeed index subscriptions."""
    feed = get_feed_client()
    return feed.get_index_value()


@mcp.tool()
def feed_unsubscribe_index_value(instruments_list: list[dict]) -> dict:
    """Unsubscribe from live index value WebSocket stream for the given indices."""
    feed = get_feed_client()
    feed.unsubscribe_index_value(instruments_list)
    return {"status": "unsubscribed", "feed": "index_value", "count": len(instruments_list)}


@mcp.tool()
def feed_subscribe_market_depth(instruments_list: list[dict]) -> dict:
    """
    Subscribe to live 5-level buy/sell market depth for equity/FNO instruments
    (e.g., [{"exchange": "NSE", "segment": "CASH", "exchange_token": "2885"}]).
    """
    feed = get_feed_client()
    feed.subscribe_market_depth(instruments_list)
    return {"status": "subscribed", "feed": "market_depth", "count": len(instruments_list)}


@mcp.tool()
def feed_get_market_depth() -> dict:
    """Poll the latest received market depth (buyBook & sellBook) from active GrowwFeed subscriptions."""
    feed = get_feed_client()
    return feed.get_market_depth()


@mcp.tool()
def feed_unsubscribe_market_depth(instruments_list: list[dict]) -> dict:
    """Unsubscribe from live market depth WebSocket stream for the given instruments."""
    feed = get_feed_client()
    feed.unsubscribe_market_depth(instruments_list)
    return {"status": "unsubscribed", "feed": "market_depth", "count": len(instruments_list)}


@mcp.tool()
def feed_subscribe_equity_order_updates() -> dict:
    """Subscribe to real-time equity (CASH) order execution updates."""
    feed = get_feed_client()
    feed.subscribe_equity_order_updates()
    return {"status": "subscribed", "feed": "equity_order_updates"}


@mcp.tool()
def feed_get_equity_order_update() -> dict:
    """Poll the latest equity order update from GrowwFeed."""
    feed = get_feed_client()
    return feed.get_equity_order_update()


@mcp.tool()
def feed_unsubscribe_equity_order_updates() -> dict:
    """Unsubscribe from real-time equity order updates."""
    feed = get_feed_client()
    feed.unsubscribe_equity_order_updates()
    return {"status": "unsubscribed", "feed": "equity_order_updates"}


@mcp.tool()
def feed_subscribe_fno_order_updates() -> dict:
    """Subscribe to real-time derivatives (FNO) order execution updates."""
    feed = get_feed_client()
    feed.subscribe_fno_order_updates()
    return {"status": "subscribed", "feed": "fno_order_updates"}


@mcp.tool()
def feed_get_fno_order_update() -> dict:
    """Poll the latest F&O order update from GrowwFeed."""
    feed = get_feed_client()
    return feed.get_fno_order_update()


@mcp.tool()
def feed_unsubscribe_fno_order_updates() -> dict:
    """Unsubscribe from real-time F&O order updates."""
    feed = get_feed_client()
    feed.unsubscribe_fno_order_updates()
    return {"status": "unsubscribed", "feed": "fno_order_updates"}


@mcp.tool()
def feed_subscribe_fno_position_updates() -> dict:
    """Subscribe to real-time derivatives (FNO) position updates."""
    feed = get_feed_client()
    feed.subscribe_fno_position_updates()
    return {"status": "subscribed", "feed": "fno_position_updates"}


@mcp.tool()
def feed_get_fno_position_update() -> dict:
    """Poll the latest F&O position update from GrowwFeed."""
    feed = get_feed_client()
    return feed.get_fno_position_update()


@mcp.tool()
def feed_unsubscribe_fno_position_updates() -> dict:
    """Unsubscribe from real-time F&O position updates."""
    feed = get_feed_client()
    feed.unsubscribe_fno_position_updates()
    return {"status": "unsubscribed", "feed": "fno_position_updates"}


# =====================================================================
# 9. USER PROFILE
# =====================================================================

@mcp.tool()
def get_user_profile() -> dict:
    """Retrieve authenticated user account details (UCC, active segments, NSE/BSE & DDPI status)."""
    groww = get_groww_client()
    return groww.get_user_profile()


if __name__ == "__main__":
    mcp.run()