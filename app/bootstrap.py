from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Asset, AssetKind


DEFAULT_CRYPTO_ASSETS = [
    {"symbol": "BTC", "name": "Bitcoin", "external_id": "bitcoin", "kind": AssetKind.CRYPTO},
    {"symbol": "ETH", "name": "Ethereum", "external_id": "ethereum", "kind": AssetKind.CRYPTO},
    {"symbol": "SOL", "name": "Solana", "external_id": "solana", "kind": AssetKind.CRYPTO},
    {"symbol": "LINK", "name": "Chainlink", "external_id": "chainlink", "kind": AssetKind.CRYPTO},
]

DEFAULT_ETF_ASSETS = [
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "external_id": "SPY", "kind": AssetKind.ETF},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "external_id": "QQQ", "kind": AssetKind.ETF},
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "external_id": "VTI", "kind": AssetKind.ETF},
]

DEFAULT_STOCK_ASSETS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "external_id": "AAPL", "kind": AssetKind.STOCK},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "external_id": "MSFT", "kind": AssetKind.STOCK},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "external_id": "NVDA", "kind": AssetKind.STOCK},
]


def seed_assets(db: Session, watchlist: list[str], etf_watchlist: list[str], stock_watchlist: list[str]) -> None:
    wanted = {item.upper() for item in watchlist}
    wanted_etfs = {item.upper() for item in etf_watchlist}
    wanted_stocks = {item.upper() for item in stock_watchlist}
    for asset_data in DEFAULT_CRYPTO_ASSETS + DEFAULT_ETF_ASSETS + DEFAULT_STOCK_ASSETS:
        if asset_data["kind"] == AssetKind.CRYPTO:
            allowed = wanted
        elif asset_data["kind"] == AssetKind.ETF:
            allowed = wanted_etfs
        else:
            allowed = wanted_stocks
        if asset_data["symbol"] not in allowed:
            continue
        exists = db.scalar(select(Asset).where(Asset.symbol == asset_data["symbol"]))
        if exists:
            continue
        db.add(
            Asset(
                symbol=asset_data["symbol"],
                name=asset_data["name"],
                external_id=asset_data["external_id"],
                kind=asset_data["kind"],
            )
        )
    db.commit()
