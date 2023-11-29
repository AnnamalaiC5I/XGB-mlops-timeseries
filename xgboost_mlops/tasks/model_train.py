from time_series_databricks.common import Task
import statsmodels.api as sm
import pandas as pd
import matplotlib.pyplot as plt
from pyspark.sql import SparkSession
from pyspark.dbutils import DBUtils
import boto3
from io import BytesIO
from mlflow.tracking.client import MlflowClient
from sklearn.model_selection import train_test_split
import mlflow
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.graphics.tsaplots import plot_pacf, plot_acf


import warnings
warnings.filterwarnings('ignore')

from databricks import feature_store
from databricks.feature_store import feature_table, FeatureLookup
fs = feature_store.FeatureStoreClient()

class ModelTrain(Task):

    def train_model(self, X_train, X_test, partition, training_set, fs):
                       
                        mlflow.set_experiment(self.conf['Mlflow']['experiment_name'])
                        with mlflow.start_run(run_name=self.conf['Mlflow']['run_name']) as run:
                                
                                pass
                                # fs.log_model(
                                # model=model,
                                # artifact_path="timeseries_prediction",
                                # flavor=mlflow.statsmodels,
                                # training_set=training_set,
                                # registered_model_name=self.conf['Mlflow']['register_model'],
                                # )
                                

                                #mlflow.statsmodels.log_model(results, artifact_path=self.conf['Mlflow']['artifact_path'], registered_model_name = self.conf['Mlflow']['register_model'])
    
    def load_data(self, inference_data_df):
                    

                    training_pd = inference_data_df.toPandas()
                
                    length = len(training_pd)
                    train_size=0.8
                    partition = length*train_size
                    
                    X_train, X_test= training_pd.iloc[:int(partition),:],training_pd.iloc[int(partition):,:]

                    return X_train, X_test, inference_data_df, partition

    def _train_model(self):
                spark = SparkSession.builder.appName("CSV Loading Example").getOrCreate()

                dbutils = DBUtils(spark)

                inference_data_df = fs.read_table('default.timeseries')

                X_train, X_test, training_set, partition = self.load_data(inference_data_df)

                X_train.set_index("Month",inplace=True)

                X_test.set_index("Month",inplace=True)
        
                client = MlflowClient()
 

                self.train_model(X_train, X_test, partition, training_set, fs)



    def launch(self):
         
         self._train_model()


def entrypoint():
         task = ModelTrain()
         task.launch()


if __name__ == '__main__':
    entrypoint()
          

