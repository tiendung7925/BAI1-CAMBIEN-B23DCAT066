import logging
import warnings
import os
import numpy as np
import pandas as pd

from scipy import stats

from sklearn.preprocessing import StandardScaler

from influxdb_client import (
    InfluxDBClient,
    Point
)

from influxdb_client.client.write_api import (
    SYNCHRONOUS
)

from influxdb_client.client.warnings import (
    MissingPivotFunction
)


# =====================================================
# CONFIG
# =====================================================

INFLUX_URL = (
    "http://localhost:8086"
)

os.getenv("INFLUX_TOKEN")

INFLUX_ORG = "PTIT"

INFLUX_BUCKET = "iot_data"

STUDENT_ID = "B23DCAT066"

RAW_MEASUREMENT = (
    "environment"
)

CLEAN_MEASUREMENT = (
    "environment_clean"
)


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(

    level=logging.INFO,

    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    )
)


warnings.simplefilter(
    "ignore",
    MissingPivotFunction
)


# =====================================================
# INFLUX
# =====================================================

client = InfluxDBClient(

    url=INFLUX_URL,

    token=INFLUX_TOKEN,

    org=INFLUX_ORG,

    timeout=20000
)


query_api = (
    client.query_api()
)


write_api = (
    client.write_api(
        write_options=SYNCHRONOUS
    )
)


# =====================================================
# 1. QUERY RAW DATA
# =====================================================

def query_raw_data():

    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -1h)

      |> filter(
          fn: (r) =>
            r["_measurement"]
            == "{RAW_MEASUREMENT}"
      )

      |> filter(
          fn: (r) =>
            r["student_id"]
            == "{STUDENT_ID}"
      )

      |> pivot(
          rowKey: ["_time", "device_id"],
          columnKey: ["_field"],
          valueColumn: "_value"
      )

      |> sort(
          columns: ["_time"]
      )
    '''


    result = (
        query_api
        .query_data_frame(query)
    )


    if isinstance(
        result,
        list
    ):

        frames = [

            frame

            for frame in result

            if not frame.empty
        ]


        if not frames:

            return pd.DataFrame()


        return pd.concat(
            frames,
            ignore_index=False
        )


    return result


# =====================================================
# 2. CLEAN DATA
# =====================================================

def clean_dataframe(df):

    if df.empty:

        return df


    required = [

        "_time",

        "temperature",

        "humidity"
    ]


    # ---------------------------------------------
    # Check required columns
    # ---------------------------------------------

    for column in required:

        if column not in df.columns:

            raise ValueError(

                f"Missing required "
                f"column: {column}"
            )


    optional = [

        "distance",

        "latency_ms",

        "sequence"
    ]


    columns = (

        required

        +

        [
            column

            for column in optional

            if column in df.columns
        ]
    )


    df = (
        df[columns]
        .copy()
    )


    # ---------------------------------------------
    # Time
    # ---------------------------------------------

    df["_time"] = (
        pd.to_datetime(
            df["_time"],
            utc=True
        )
    )


    df = (
        df
        .sort_values("_time")
    )


    # ---------------------------------------------
    # Remove duplicate timestamps
    # ---------------------------------------------

    df = (
        df
        .drop_duplicates(
            subset=["_time"],
            keep="last"
        )
    )


    df = (
        df
        .set_index("_time")
    )


    # ---------------------------------------------
    # Convert numeric
    # ---------------------------------------------

    numeric_columns = [

        column

        for column in df.columns

        if column != "device_id"
    ]


    for column in numeric_columns:

        df[column] = pd.to_numeric(

            df[column],

            errors="coerce"
        )


    # ---------------------------------------------
    # Missing values
    # ---------------------------------------------

    df[numeric_columns] = (

        df[numeric_columns]

        .interpolate(

            method="time",

            limit_direction="both"
        )
    )


    df[numeric_columns] = (

        df[numeric_columns]

        .bfill()

        .ffill()
    )


    return df


# =====================================================
# 3. OUTLIER - Z SCORE
# =====================================================

def remove_outliers_zscore(

    df,

    columns,

    threshold=3.0
):

    df = df.copy()

    total_outliers = 0


    for column in columns:

        if column not in df.columns:

            continue


        values = (
            df[column]
            .astype(float)
        )


        # Không đủ dữ liệu

        if len(values) < 3:

            continue


        # Std = 0

        if values.std(
            ddof=0
        ) == 0:

            continue


        z = np.abs(

            stats.zscore(

                values,

                nan_policy="omit"
            )
        )


        mask = (

            np.nan_to_num(

                z,

                nan=0.0
            )

            > threshold
        )


        count = int(
            mask.sum()
        )


        total_outliers += count


        if count > 0:

            replacement = (

                values[
                    ~mask
                ]
                .median()
            )


            if pd.isna(
                replacement
            ):

                replacement = (
                    values.median()
                )


            df.loc[
                mask,
                column
            ] = replacement


    logging.info(

        "Outliers removed/replaced: %d",

        total_outliers
    )


    return df


# =====================================================
# 4. RESAMPLING + FEATURES
# =====================================================

def resample_and_features(df):

    numeric_columns = [

        column

        for column in [

            "temperature",

            "humidity",

            "distance",

            "latency_ms"

        ]

        if column in df.columns
    ]


    # ---------------------------------------------
    # Resampling 1 minute
    # ---------------------------------------------

    result = (

        df[numeric_columns]

        .resample("1min")

        .mean()
    )


    # ---------------------------------------------
    # Missing after resampling
    # ---------------------------------------------

    result = (

        result

        .interpolate(

            method="time",

            limit_direction="both"
        )

        .bfill()

        .ffill()
    )


    # ---------------------------------------------
    # Rolling mean 3 minutes
    # ---------------------------------------------

    result[
        "temp_rolling_mean_3m"
    ] = (

        result[
            "temperature"
        ]

        .rolling(

            window=3,

            min_periods=1
        )

        .mean()
    )


    # ---------------------------------------------
    # Delta
    # ---------------------------------------------

    result[
        "temp_delta"
    ] = (

        result[
            "temperature"
        ]

        .diff()

        .fillna(0)
    )


    # =================================================
    # STANDARDIZATION
    # =================================================

    normalize_columns = [

        column

        for column in [

            "temperature",

            "humidity",

            "distance",

            "latency_ms"

        ]

        if column in result.columns
    ]


    if normalize_columns:

        scaler = (
            StandardScaler()
        )


        normalized = (
            scaler.fit_transform(
                result[
                    normalize_columns
                ]
            )
        )


        for i, column in enumerate(
            normalize_columns
        ):

            result[
                f"{column}_norm"
            ] = normalized[:, i]


    return result.dropna(
        how="all"
    )


# =====================================================
# 5. WRITE CLEAN DATA
# =====================================================

def write_clean_data(df):

    if df.empty:

        logging.info(
            "No clean data."
        )

        return


    written = 0


    for timestamp, row in (
        df.iterrows()
    ):

        point = (

            Point(
                CLEAN_MEASUREMENT
            )

            .tag(
                "student_id",
                STUDENT_ID
            )

            .field(
                "temperature",
                float(
                    row["temperature"]
                )
            )

            .field(
                "humidity",
                float(
                    row["humidity"]
                )
            )

            .field(
                "temp_rolling_mean_3m",
                float(
                    row[
                        "temp_rolling_mean_3m"
                    ]
                )
            )

            .field(
                "temp_delta",
                float(
                    row["temp_delta"]
                )
            )
        )


        optional_fields = [

            "distance",

            "latency_ms",

            "temperature_norm",

            "humidity_norm",

            "distance_norm",

            "latency_ms_norm"
        ]


        for field_name in optional_fields:

            if (

                field_name in row.index

                and

                pd.notna(
                    row[field_name]
                )
            ):

                point.field(

                    field_name,

                    float(
                        row[field_name]
                    )
                )


        point.time(
            timestamp.to_pydatetime()
        )


        write_api.write(

            bucket=INFLUX_BUCKET,

            org=INFLUX_ORG,

            record=point
        )


        written += 1


    logging.info(

        "Clean records written: %d",

        written
    )


# =====================================================
# 6. PIPELINE
# =====================================================

def run_pipeline():

    logging.info(
        "[1/5] Reading raw data..."
    )


    raw_df = (
        query_raw_data()
    )


    if raw_df.empty:

        logging.warning(

            "No data found."

        )

        logging.warning(

            "Run subscriber.py first."
        )

        return


    logging.info(

        "[2/5] Raw rows: %d",

        len(raw_df)
    )


    # Missing values

    df = (
        clean_dataframe(
            raw_df
        )
    )


    logging.info(

        "After missing-value "
        "processing: %d rows",

        len(df)
    )


    # Outlier

    logging.info(

        "[3/5] Detecting outliers..."
    )


    df = (
        remove_outliers_zscore(

            df,

            columns=[

                "temperature",

                "humidity",

                "distance",

                "latency_ms"
            ],

            threshold=3.0
        )
    )


    # Resampling

    logging.info(

        "[4/5] Resampling "
        "and feature engineering..."
    )


    clean_df = (
        resample_and_features(
            df
        )
    )


    logging.info(

        "After resampling: %d rows",

        len(clean_df)
    )


    logging.info(

        "Columns: %s",

        list(
            clean_df.columns
        )
    )


    # Write

    logging.info(

        "[5/5] Writing "
        "environment_clean..."
    )


    write_clean_data(
        clean_df
    )


    logging.info(

        "Pipeline completed "
        "successfully."
    )


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    try:

        run_pipeline()

    finally:

        write_api.close()

        client.close()