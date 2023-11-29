from xgboost_mlops.common import Task
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
from mlflow.models import infer_signature

import warnings
warnings.filterwarnings('ignore')

from databricks import feature_store
from databricks.feature_store import feature_table, FeatureLookup
fs = feature_store.FeatureStoreClient()

from skforecast.ForecasterAutoreg import ForecasterAutoreg
from xgboost import XGBRegressor

def ma_forecast(orginal_test_col_df,forecaster1):
    
    orginal_test_col_df_ = orginal_test_col_df.copy()
    
    len_test = len(orginal_test_col_df)
    
    forecast = []
    
    forecast = forecaster1.predict(steps=len_test, exog = orginal_test_col_df_[train_exog])
    
    forecast = forecast.values

    orginal_test_col_df_["Predicted_Demand"] = forecast

    return orginal_test_col_df_

class ModelTrain(Task):

    def train_model(self,train_y, train_X, test_y, test_X, orginal_test_col_df):
                       
                        mlflow.set_experiment(self.conf['Mlflow']['experiment_name'])
                        with mlflow.start_run(run_name=self.conf['Mlflow']['run_name']) as run:
                                
                                client = MlflowClient()
                                
                                forecaster1 = ForecasterAutoreg(
                                regressor = XGBRegressor(max_depth= 3, 
                                                        n_estimators= 200, 
                                                        learning_rate = 0.1,
                                                        alpha = 0.1,
                                                        random_state=123),
                                lags = 5
                                )
                                train_exog = self.conf['train_exog']

                                forecaster1.fit(y=train_y, exog = train_X[train_exog])

                                orginal_test_col_df_ = ma_forecast(orginal_test_col_df,forecaster1)

                                mse = mean_squared_error(orginal_test_col_df_['Order_Demand'],orginal_test_col_df_['Predicted_Demand'])
                                mae = mean_absolute_error(orginal_test_col_df_['Order_Demand'],orginal_test_col_df_['Predicted_Demand'])

                                mlflow.log_metric('mean_squared_error',mse)
                                mlflow.log_metric('mean_absolute_error',mae)

                                mlflow.log_param('max_depth',3)
                                mlflow.log_param('n_estimators',200)
                                mlflow.log_param('learning_rate',0.1)
                                mlflow.log_param('alpha',0.1)

                                fig, ax = plt.subplots(figsize=(12, 5))
                                plt.plot(train_y, label='training')
                                plt.plot(test_y, label='actual')
                                plt.plot(orginal_test_col_df_['Predicted_Demand'], label='forecast')
                                #x_loc = range(len(df1['date']))
                                #x_labels = df1['date'].dt.date
                                #plt.xticks(x_loc, x_labels, rotation='vertical')
                                plt.locator_params(axis='x', nbins=50)
                                plt.title('Forecast vs Actuals')
                                plt.legend(loc='upper left', fontsize=8)

                                mlflow.log_figure(fig,"test_vs_pred.png")

                                signature = infer_signature(train_X, forecaster1.predict(train_X))

                                mlflow.xgboost.log_model(
                                        forecaster1, "Forecaster-reg", signature=signature
                                )



                               
    
    def load_data(self, inference_data_df):
                    
                training_pd = inference_data_df.toPandas()

                train_size = 0.75
                train_end = int(len(training_pd)*train_size)
                train_df = training_pd[:train_end]
                test_df = training_pd[train_end:]

                gh_out = training_pd['Order_Demand']
                gh = training_pd.drop(['Order_Demand'],axis=1)

                train_X = train_df.drop(['Order_Demand'], axis =1)
                train_y = train_df['Order_Demand']
                test_X = test_df.drop(['Order_Demand'], axis =1 )
                test_y = test_df['Order_Demand']

                return train_X, train_y, test_X, test_y, train_df, test_df, inference_data_df

    def _train_model(self):
                spark = SparkSession.builder.appName("CSV Loading Example").getOrCreate()

                dbutils = DBUtils(spark)

                inference_data_df = fs.read_table('default.timeseries')

                train_X, train_y, test_X, test_y, train_df, test_df, training_set = self.load_data(inference_data_df)

                orginal_test_col_df= test_df[[ 'Quarter', 'Week_Number', 'Month', 'Year', 'day','dayofyear', 'weekday', 'is_month_start', 'is_month_end','contri_week_quarter', 'SI_Quarter_week','Order_Demand']]
        
                self.train_model(train_y, train_X, test_y, test_X, orginal_test_col_df)

                
 

                



    def launch(self):
         
         self._train_model()


def entrypoint():
         task = ModelTrain()
         task.launch()


if __name__ == '__main__':
    entrypoint()
          

