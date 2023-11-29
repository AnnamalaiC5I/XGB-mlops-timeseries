"""
This file configures the Python package with entrypoints used for future runs on Databricks.

Please follow the `entry_points` documentation for more details on how to configure the entrypoint:
* https://setuptools.pypa.io/en/latest/userguide/entry_point.html
"""

from setuptools import find_packages, setup
from xgboost_mlops import __version__

PACKAGE_REQUIREMENTS = ["pyyaml"]

LOCAL_REQUIREMENTS = [
    "pyspark==3.2.1",
    "boto3",
    "statsmodels",
    "skforecast",
    "xgboost",
    #"protobuf==3.20.1",
    "delta-spark==1.1.0",
    "scikit-learn==1.2.0",
    "databricks-sdk",
    "databricks-feature-store",
    #"databricks-registry-webhooks",
    "evidently",
    "pandas==1.5.3",
    "mlflow",
    "urllib3"
]

TEST_REQUIREMENTS = [
    # development & testing tools
    "pytest",
    "coverage[toml]",
    "pytest-cov",
    "dbx>=0.8",
    "statsmodels"
]

setup(
    name="xgboost_mlops",
    packages=find_packages( exclude=["tests", "tests.*"]),
    setup_requires=["setuptools","wheel"],
    install_requires=LOCAL_REQUIREMENTS,
    extras_require={"local": LOCAL_REQUIREMENTS, "test": TEST_REQUIREMENTS},
    entry_points = {
        "console_scripts": [
            "DataPreprocess = xgboost_mlops.tasks.data_preprocess:entrypoint",
            "ModelTrain = xgboost_mlops.tasks.model_train:entrypoint",
            "Webhook = xgboost_mlops.tasks.webhook:entrypoint"
    ]
    },
    version=__version__,
    description="",
    author="",
)