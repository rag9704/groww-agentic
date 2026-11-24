# Groww Trading MCP Server

A Model Context Protocol (MCP) server built with the official Groww Python SDK (`growwapi`), exposing **55 tools** for market data, instrument search, portfolio tracking, margin calculation, order execution, GTT/OCO smart orders, historical backtesting, and WebSocket streaming across **NSE** and **BSE** (`CASH` and `FNO` segments).

---

## Prerequisites

* **Python 3.9+**
* **Groww Account** with an active **Trading API Subscription** enabled on the Groww Cloud API Keys page
* **MCP Client**: Claude Code CLI, Claude Desktop, Cursor, or MCP Inspector

---

## 1. Installation

1. **Create a project folder** containing `server.py` and set up a virtual environment:
   ```bash
   mkdir -p ~/groww-mcp && cd ~/groww-mcp
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install the required dependencies**:
   ```bash
   pip install growwapi "mcp[cli]" pandas pyotp python-dotenv
   ```

---

## 2. Authentication Setup (`.env`)

Create a `.env` file in the **same directory as `server.py`**. The server automatically loads `.env` relative to `server.py` and supports three authentication flows:

### Option A: TOTP Flow (Recommended — Non-Expiring)
Generate a TOTP token and Base32 secret from the Groww Cloud API Keys dropdown:
```env
api_key=YOUR_TOTP_TOKEN
totp_secret=YOUR_BASE32_TOTP_SECRET
```

### Option B: API Key & Secret Flow (Requires Daily Approval)
Generate a standard API key and secret on Groww Cloud (must be approved daily on the Groww dashboard):
```env
api_key=YOUR_API_KEY
secret=YOUR_API_SECRET
```
> **Note:** Do not set `totp_secret` when using a standard `secret`.

### Option C: Direct Access Token
If you already generated a session token externally:
```env
access_token=YOUR_ACCESS_TOKEN
```

*(Make sure `.env` is listed in your `.gitignore` so credentials are never committed to version control.)*

---

## 3. Connecting to an MCP Client

### Claude Code (CLI)

1. **Install Claude Code** (if not already installed):
   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   ```

2. **Register the server** from your regular terminal (outside an active `claude` session), replacing `/ABSOLUTE/PATH/TO` with your actual project path:
   ```bash
   claude mcp add --transport stdio --scope user groww-trading -- /ABSOLUTE/PATH/TO/.venv/bin/python /ABSOLUTE/PATH/TO/server.py
   ```
   * Use `--scope user` to make `groww-trading` available across all your projects (`~/.claude.json`).
   * Use `--scope local` (default) to restrict it to the current directory.

3. **Verify the connection**:
   ```bash
   claude mcp list
   ```
   Confirm `groww-trading` shows **`✔ Connected`**.

4. **Start a session and inspect tools**:
   ```bash
   claude
   ```
   Inside the interactive Claude Code prompt, run `/mcp` to view all 55 registered tools.

#### Sharing via Project `.mcp.json`
To share the server configuration with teammates in a Git repository, add a `.mcp.json` file at the project root:
```json
{
  "mcpServers": {
    "groww-trading": {
      "type": "stdio",
      "command": "/ABSOLUTE/PATH/TO/.venv/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/server.py"]
    }
  }
}
```
*(Each teammate will be prompted to approve the `.mcp.json` server on their first `claude` launch and must supply their own local `.env` file.)*

---

### Claude Desktop / Cursor

Add the following entry to your client's MCP configuration file (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "groww-trading": {
      "command": "/ABSOLUTE/PATH/TO/.venv/bin/python",
      "args": ["/ABSOLUTE/PATH/TO/server.py"]
    }
  }
}
```
Restart the application after saving.

---

### MCP Inspector (Testing & Debugging)

Test any tool interactively in your browser without using `uv` by passing your `.venv` Python binary directly:

```bash
npx @modelcontextprotocol/inspector /ABSOLUTE/PATH/TO/.venv/bin/python /ABSOLUTE/PATH/TO/server.py
```

---

## 4. Available Tools (55 Total)

### Session & Account (2)
| Tool | Description |
| :--- | :--- |
| `refresh_groww_session` | Re-authenticate and refresh the cached Groww API access token and WebSocket client |
| `get_user_profile` | Fetch UCC, active segments (`CASH`, `FNO`), exchange permissions, and DDPI status |

### Instruments (6)
| Tool | Description |
| :--- | :--- |
| `get_instrument_by_symbol` | Lookup instrument metadata by Groww symbol (e.g., `NSE-RELIANCE`, `NSE-NIFTY-30Sep25-FUT`) |
| `get_instrument_by_trading_symbol_and_exchange` | Lookup instrument by exchange (`NSE`/`BSE`) and trading symbol (`RELIANCE`) |
| `get_instrument_by_exchange_token` | Lookup instrument by numeric exchange token (e.g., `2885`) |
| `get_all_instruments` | Search and filter all tradable instruments by keyword, exchange, segment, type (`EQ`, `IDX`, `FUT`, `CE`, `PE`), underlying, or expiry |
| `get_instrument_csv_url` | Get the direct download URL (`INSTRUMENT_CSV_URL`) for Groww's full instrument master CSV |
| `load_raw_instruments` | Load instrument records directly via `groww._load_instruments()` |

### Live Market Data (5)
| Tool | Description |
| :--- | :--- |
| `get_quote` | Real-time quote including LTP, OHLC, market depth, OI, volume, and 52-week high/low |
| `get_ltp` | Batch Last Traded Price for up to 50 instruments (`["NSE_NIFTY", "NSE_RELIANCE"]`) |
| `get_ohlc` | Batch real-time snapshot OHLC for up to 50 instruments |
| `get_option_chain` | Complete option chain (CE/PE strikes with LTP, OI, volume, IV, and Greeks) for an underlying and expiry |
| `get_greeks` | Option Greeks (`delta`, `gamma`, `theta`, `vega`, `rho`, `iv`) for a specific F&O contract |

### Portfolio & Margin (5)
| Tool | Description |
| :--- | :--- |
| `get_holdings` | Fetch long-term DEMAT equity holdings, pledged/locked quantities, and average prices |
| `get_positions` | Fetch open positions across `CASH`, `FNO`, or both segments |
| `get_position_for_trading_symbol` | Fetch position details and realised P&L for a single symbol |
| `get_available_margin_details` | Fetch clear cash, collateral, CNC/MIS equity balances, and F&O SPAN/exposure margin |
| `get_order_margin_details` | Calculate required margin and brokerage charges for a single order or F&O basket |

### Orders (8)
| Tool | Description |
| :--- | :--- |
| `place_order` | Place a `CASH` or `FNO` order (`LIMIT`, `MARKET`, `SL`, `SL_M`; `CNC`, `MIS`, `NRML`) |
| `modify_order` | Modify quantity, order type, price, or trigger price of an open order |
| `cancel_order` | Cancel an open or pending order by `groww_order_id` |
| `get_trade_list_for_order` | List executed trades for a given `groww_order_id` |
| `get_order_status` | Check order status and filled quantity by `groww_order_id` |
| `get_order_status_by_reference` | Check order status using your custom `order_reference_id` |
| `get_order_list` | List all orders placed today (optionally filtered by segment) |
| `get_order_detail` | Fetch full order metadata and timestamps by `groww_order_id` |

### Smart Orders — GTT & OCO (7)
| Tool | Description |
| :--- | :--- |
| `create_gtt_smart_order` | Create a Good-Till-Triggered order (1-year default validity) with `UP`/`DOWN` trigger |
| `create_oco_smart_order` | Create a One-Cancels-Other target + stop-loss order to protect/exit an existing position |
| `modify_gtt_smart_order` | Update quantity, trigger price/direction, or limit price of an active GTT order |
| `modify_oco_smart_order` | Update quantity, duration, product type, or target/stop-loss triggers on an OCO order |
| `cancel_smart_order` | Cancel an active `GTT` or `OCO` smart order |
| `get_smart_order` | Retrieve full details of a single smart order by ID |
| `get_smart_order_list` | Filter and paginate smart orders by segment, type, status, and date range |

### Historical Data & Backtesting (4)
| Tool | Description |
| :--- | :--- |
| `get_expiries` | List available F&O expiry dates (`YYYY-MM-DD`) for an underlying from 2020 onward |
| `get_contracts` | List available F&O contract Groww symbols for a given underlying and expiry date |
| `get_historical_candles` | Fetch OHLCV (+ OI for F&O) candles from `1minute` up to `1month` intervals |
| `get_historical_candle_data_legacy` | Legacy historical candle endpoint using `trading_symbol` and `interval_in_minutes` |

### WebSocket Streaming Feed (18)
Stateful `GrowwFeed` subscribe / poll / unsubscribe triplets (up to 1,000 instruments per stream):
* **LTP Stream**: `feed_subscribe_ltp`, `feed_get_ltp`, `feed_unsubscribe_ltp`
* **Index Stream**: `feed_subscribe_index_value`, `feed_get_index_value`, `feed_unsubscribe_index_value`
* **Market Depth (5-Level)**: `feed_subscribe_market_depth`, `feed_get_market_depth`, `feed_unsubscribe_market_depth`
* **Equity Order Updates**: `feed_subscribe_equity_order_updates`, `feed_get_equity_order_update`, `feed_unsubscribe_equity_order_updates`
* **F&O Order Updates**: `feed_subscribe_fno_order_updates`, `feed_get_fno_order_update`, `feed_unsubscribe_fno_order_updates`
* **F&O Position Updates**: `feed_subscribe_fno_position_updates`, `feed_get_fno_position_update`, `feed_unsubscribe_fno_position_updates`

---

## 5. Example Prompts

Once connected in Claude Code or Claude Desktop, try asking:
* *"Check my Groww DEMAT holdings, open positions, and available margin."*
* *"Fetch the live quote for RELIANCE on NSE and check how much CNC margin is required to buy 10 shares."*
* *"Get the upcoming NIFTY expiry dates and show me the option chain with Greeks for the nearest expiry."*
* *"Fetch 30-minute historical candles for `NSE-WIPRO` over the last 5 trading days."*
* *"Set a GTT buy order for 5 shares of TCS on NSE if the price drops to ₹3,850."*

---

## 6. Rate Limits & Safety Notice

### Groww API Rate Limits
Rate limits are enforced per API category:
* **Authentication**: 30 requests / minute
* **Orders** (Place, Modify, Cancel): 10 requests / second, 250 requests / minute
* **Live Data** (Quote, LTP, OHLC): 10 requests / second, 300 requests / minute
* **Non-Trading** (Positions, Holdings, Margin, Order Lists): 20 requests / second, 500 requests / minute

### Disclaimer
This server executes live financial actions on your Groww brokerage account. Always keep manual approval prompts enabled in your MCP client for order-mutating tools (`place_order`, `modify_order`, `cancel_order`, `create_gtt_smart_order`, `create_oco_smart_order`).