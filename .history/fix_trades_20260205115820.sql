-- Fix missing trades from Alpaca orders
DECLARE @SessionId VARCHAR(50) = 'WH-00be3941';

-- First, delete the incomplete manual entry if it exists
DELETE FROM dbo.Trades WHERE TradeId = 284942;

-- Trade 1: Feb 4 - BUY TQQQ 1122 @ ~50.97, EXIT @ ~51.76
INSERT INTO dbo.Trades (Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, ExitTime, ExitPrice, ExitQuantity, ExitReason, SessionId, CreatedAt)
VALUES ('TQQQ', 'LONG', '2026-02-04 15:00:14.954839', 50.97, 1122, '2026-02-04 19:30:04.466993', 51.76, 1122, 'Webhook:EXIT', @SessionId, GETDATE());

-- Trade 2: Feb 4-5 - BUY SQQQ 795 @ ~15.48, EXIT @ ~15.23
INSERT INTO dbo.Trades (Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, ExitTime, ExitPrice, ExitQuantity, ExitReason, SessionId, CreatedAt)
VALUES ('SQQQ', 'LONG', '2026-02-04 20:00:03.971260', 15.48, 795, '2026-02-05 14:35:10.435042', 15.23, 795, 'Webhook:EXIT', @SessionId, GETDATE());

-- Trade 3: Feb 5 - BUY TQQQ 1189 @ ~48.40, EXIT @ ~47.51
INSERT INTO dbo.Trades (Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, ExitTime, ExitPrice, ExitQuantity, ExitReason, SessionId, CreatedAt)
VALUES ('TQQQ', 'LONG', '2026-02-05 15:00:31.985271', 48.40, 1189, '2026-02-05 15:15:09.678342', 47.51, 1189, 'Webhook:EXIT', @SessionId, GETDATE());

-- Trade 4: Feb 5 - BUY TQQQ 1190 @ ~47.63, EXIT @ ~48.56
INSERT INTO dbo.Trades (Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, ExitTime, ExitPrice, ExitQuantity, ExitReason, SessionId, CreatedAt)
VALUES ('TQQQ', 'LONG', '2026-02-05 15:20:05.808122', 47.63, 1190, '2026-02-05 16:35:05.863057', 48.56, 1190, 'Webhook:EXIT', @SessionId, GETDATE());

-- Calculate and update P&L for all trades
UPDATE dbo.Trades
SET 
    GrossPnL = (ExitPrice - EntryPrice) * ExitQuantity,
    NetPnL = (ExitPrice - EntryPrice) * ExitQuantity,
    PnLPercent = ((ExitPrice - EntryPrice) / EntryPrice) * 100,
    DurationMinutes = DATEDIFF(MINUTE, EntryTime, ExitTime)
WHERE SessionId = @SessionId AND ExitTime IS NOT NULL;

SELECT TradeId, Symbol, Direction, EntryTime, EntryPrice, EntryQuantity, ExitTime, ExitPrice, NetPnL, PnLPercent, DurationMinutes
FROM dbo.Trades WHERE SessionId = @SessionId ORDER BY EntryTime;
