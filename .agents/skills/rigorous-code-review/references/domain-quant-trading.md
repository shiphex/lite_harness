# Domain Overlay: Quantitative / Trading Systems

Apply to market data, research, backtests, portfolio logic, order management, execution, reconciliation, and risk systems.

Check:

- look-ahead or target leakage;
- survivorship bias;
- timestamp, timezone, trading-calendar, and session alignment;
- corporate actions and revised historical data;
- transaction cost, slippage, latency, and liquidity assumptions;
- order lifecycle;
- duplicate submission and retry idempotency;
- cancel/replace races;
- position, cash, PnL, fees, and reconciliation;
- precision and rounding;
- hard position/loss/exposure/rate limits;
- stale market data and disconnect behavior;
- backtest/live parity;
- kill switch and recovery after partial execution.

Financial correctness and risk controls are merge-blocking concerns.

For backtests, ask:

- Could the strategy observe information unavailable at decision time?
- Are universe constituents historically correct?
- Are fills modeled realistically enough for the claimed conclusion?
- Are costs and rejected orders included?
- Is the result robust to timestamp alignment and data revisions?
