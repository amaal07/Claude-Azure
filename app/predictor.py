import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.ensemble import GradientBoostingRegressor
from datetime import datetime, timedelta


FEATURE_COLS = [
    "ma7", "ma21", "ma50",
    "rsi", "macd", "macd_signal",
    "returns", "volatility_7", "momentum_14",
    "lag_1", "lag_2", "lag_3", "lag_5", "lag_10",
    "volume_norm",
]


def fetch_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol and try again.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    close = df["Close"].squeeze()
    volume = df["Volume"].squeeze()

    df["ma7"] = close.rolling(7).mean()
    df["ma21"] = close.rolling(21).mean()
    df["ma50"] = close.rolling(50).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    df["returns"] = close.pct_change()
    df["volatility_7"] = df["returns"].rolling(7).std()
    df["momentum_14"] = close / close.shift(14) - 1

    for lag in [1, 2, 3, 5, 10]:
        df[f"lag_{lag}"] = close.shift(lag)

    vol_mean = volume.rolling(20).mean()
    df["volume_norm"] = volume / vol_mean.replace(0, np.nan)

    df.dropna(inplace=True)
    return df


def train_model(df: pd.DataFrame):
    X = df[FEATURE_COLS].values
    y = df["Close"].squeeze().values

    split = int(len(X) * 0.85)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = GradientBoostingRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    test_preds = model.predict(X_test)
    mape = np.mean(np.abs((y_test - test_preds) / y_test)) * 100
    accuracy = round(max(0.0, 100 - mape), 1)

    return model, accuracy


def predict_stock(ticker: str, days: int = 7) -> dict:
    df_raw = fetch_data(ticker)
    df = build_features(df_raw)

    model, accuracy = train_model(df)

    current_price = float(df["Close"].squeeze().iloc[-1])
    all_prices = list(df["Close"].squeeze().values)

    pred_prices = []
    pred_dates = []
    last_row_feat = df[FEATURE_COLS].iloc[-1].values.copy()

    lag_indices = {1: 9, 2: 10, 3: 11, 5: 12, 10: 13}

    for i in range(1, days + 1):
        feat = last_row_feat.copy()
        combined = all_prices + pred_prices
        for lag, idx in lag_indices.items():
            if len(combined) >= lag:
                feat[idx] = combined[-lag]

        next_price = float(model.predict([feat])[0])
        pred_prices.append(round(next_price, 2))
        pred_dates.append((datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d"))

    hist = df["Close"].squeeze().iloc[-60:]
    hist_dates = [d.strftime("%Y-%m-%d") for d in hist.index]
    hist_prices = [round(float(p), 2) for p in hist.values]

    last_pred = pred_prices[-1]
    change_pct = round((last_pred - current_price) / current_price * 100, 2)

    return {
        "ticker": ticker.upper(),
        "current_price": round(current_price, 2),
        "predictions": pred_prices,
        "dates": pred_dates,
        "hist_dates": hist_dates,
        "hist_prices": hist_prices,
        "accuracy": accuracy,
        "trend": "UP" if last_pred > current_price else "DOWN",
        "change_pct": change_pct,
    }