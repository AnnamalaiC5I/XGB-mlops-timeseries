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
                                
                                total_length = len(X_train)+len(X_test)
                                target = self.conf['target']
                                order = (1,1,1)
                                sorder = (1,1,1,12)
                        
                                model = sm.tsa.statespace.SARIMAX(X_train[target], order=order, seasonal_order=sorder)
                                results = model.fit()

                                

                                #y_pred = LR_Classifier.predict(X_test)
                                df1=pd.DataFrame(X_test[target])
                                df2=pd.DataFrame(results.predict(start=int(partition),end=total_length-1))

                                df2 = df2.reset_index()
                                df2.columns = ['Month','predicted_mean']

                                df1.reset_index(inplace=True)

                                df1['Month'] = pd.to_datetime(df1['Month'])
                                df2['Month'] = pd.to_datetime(df2['Month'])

                                # Now, you can proceed with the merge
                                merged_df = pd.merge(df1, df2, on='Month')


                                mae = mean_absolute_error(merged_df[target],merged_df['predicted_mean'])
                                mse = mean_squared_error(merged_df[target],merged_df['predicted_mean'])
                        
                                mlflow.log_metric("mean_squared_error", mse)
                                mlflow.log_metric("mean_absolute_error", mae)
                                
                                mlflow.log_param("order",order)
                                mlflow.log_param("seasoal_order",sorder)


                                #---------if you get error comment this lines - not tested yet---------------#
                                X_train['Seasonal first diff.'] = X_train[target] - X_train[target].shift(12)

                                fig = plt.figure(figsize = (12,8))
                                ax1 = fig.add_subplot(211)
                                fig = plot_acf(X_train['Seasonal first diff.'].iloc[13:], lags=30, ax=ax1)

                                ax2 = fig.add_subplot(212)
                                fig = plot_pacf(X_train['Seasonal first diff.'].iloc[13:], lags=30, ax=ax2)

                                mlflow.log_figure(fig,'acf_pacf_plot.png')
                                #----------------------------------------------------------------------------#
                        
                                fs.log_model(
                                model=results,
                                artifact_path="timeseries_prediction",
                                flavor=mlflow.statsmodels,
                                training_set=training_set,
                                registered_model_name=self.conf['Mlflow']['register_model'],
                                )
                                

                                #mlflow.statsmodels.log_model(results, artifact_path=self.conf['Mlflow']['artifact_path'], registered_model_name = self.conf['Mlflow']['register_model'])
    
    def load_data(self, inference_data_df):
                    # In the FeatureLookup, if you do not provide the `feature_names` parameter, all features except primary keys are returned
                    # model_feature_lookups = [FeatureLookup(table_name=table_name, lookup_key=lookup_key)]
                
                    # # fs.create_training_set looks up features in model_feature_lookups that match the primary key from inference_data_df
                    # training_set = fs.create_training_set(inference_data_df, model_feature_lookups, label=target,exclude_columns=lookup_key)
                    # training_pd = training_set.load_df().toPandas()

                    # training_pd = inference_data_df.load_df().toPandas()

                    training_pd = inference_data_df.toPandas()
                
                    # Create train and test datasets
                    length = len(training_pd)
                    train_size=0.8
                    partition = length*train_size
                    
                    X_train, X_test= training_pd.iloc[:int(partition),:],training_pd.iloc[int(partition):,:]

                    return X_train, X_test, inference_data_df, partition

    def _train_model(self):
                spark = SparkSession.builder.appName("CSV Loading Example").getOrCreate()

                dbutils = DBUtils(spark)

                # aws_access_key = dbutils.secrets.get(scope="secrets-scope", key="aws-access-key")
                # aws_secret_key = dbutils.secrets.get(scope="secrets-scope", key="aws-secret-key")
                
                # s3 = boto3.resource("s3",aws_access_key_id=aws_access_key, 
                #       aws_secret_access_key=aws_secret_key, 
                #       region_name='ap-south-1')
                
                # bucket_name =  self.conf['s3']['bucket_name']
                # csv_file_key = self.conf['preprocessed']['preprocessed_df_path']

                # s3_object = s3.Object(bucket_name, csv_file_key)
                
                # csv_content = s3_object.get()['Body'].read()

                # df_input = pd.read_csv(BytesIO(csv_content))

                # df_input_spark = spark.createDataFrame(df_input)

                # inference_data_df = df_input_spark.select(self.conf['feature-store']['lookup_key'], self.conf['target'])

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
          

