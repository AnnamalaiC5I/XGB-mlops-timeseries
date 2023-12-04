import numpy as np
from sklearn import datasets
from xgboost_mlops.common import Task
from sklearn.preprocessing import OrdinalEncoder, OneHotEncoder
import warnings
import os
import boto3
import urllib
import pickle
from pyspark.sql import SparkSession
from io import BytesIO
from databricks.feature_store.online_store_spec import AmazonDynamoDBSpec
import uuid

from databricks import feature_store

from sklearn.model_selection import train_test_split

from databricks.feature_store import feature_table, FeatureLookup

import os
import datetime
from pyspark.dbutils import DBUtils

import pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from pandas.tseries.offsets import DateOffset

from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_pacf, plot_acf
import statsmodels.api as sm






#warnings
warnings.filterwarnings('ignore')

def date_vars(df):
    df['Quarter'] = df['date'].dt.quarter
    df['Week_Number'] = df['date'].dt.week
    df['Month'] = pd. DatetimeIndex(df['date']).month
    df['Year'] = pd. DatetimeIndex(df['date']).year
    df['day'] = pd.DatetimeIndex(df['date']).day
    df['dayofyear'] = pd.DatetimeIndex(df['date']).dayofyear
    df['weekday'] = pd.DatetimeIndex(df['date']).weekday
    df['is_month_start'] = pd.DatetimeIndex(df['date']).is_month_start
    df['is_month_end'] = pd.DatetimeIndex(df['date']).is_month_end
    df["is_month_start"] = df["is_month_start"].astype(int)
    df["is_month_end"] = df["is_month_end"].astype(int)
    
    return df

def feature_engg(df):
       df_month = df.groupby(['Year','Quarter','Month'],as_index=False, sort=False).agg({'Sales':'sum'})
       df_month.rename({'Sales': 'Sales_month'}, axis=1, inplace=True)


       df_qtr = df.groupby(['Year','Quarter'],as_index=False, sort=False).agg({'Sales':'sum'})
       df_qtr.rename({'Sales': 'Sales_qtr'}, axis=1, inplace=True)

       df = df.merge(df_month[['Year','Quarter','Month','Sales_month']])
       df = df.merge(df_qtr[['Year','Quarter','Sales_qtr']])

       #df['contri_week_month'] = df.apply(lambda X: 0 if(X['Sales'] == 0) else X['Sales'] / float(X['Sales_month']), axis=1)
       # # contribution weekly & quarterly level
       #final_data['contri_week_quarter'] = final_data.apply(lambda X: X['CA'] / float(X['CA_qtr']), axis=1)
       df['contri_week_quarter'] =df.apply(lambda X: 0 if(X['Sales'] == 0) else X['Sales'] / float(X['Sales_qtr']), axis=1)
       SI_week = df.groupby(['Quarter','Week_Number'],as_index=False, sort=False).agg({'Sales':'sum'})
       # SI_week['SI_week'] = 
       SI_week['SI_Quarter_week']= SI_week['Sales']/(SI_week['Sales'].mean())
       df1 = df.merge(SI_week[['Quarter','Week_Number','SI_Quarter_week']])
       df1 = df1.sort_values(by='date')
       df1.insert(0, 'date', df1.pop('date'))
       df1.insert(1, 'Sales', df1.pop('Sales'))
       df1.drop(["Sales_month", "Sales_qtr"], axis = 1, inplace = True)

       return df1


class DataPreprocess(Task):

    def push_df_to_s3(self,df,access_key,secret_key):
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()

            s3 = boto3.resource("s3",aws_access_key_id=access_key, 
                      aws_secret_access_key=secret_key, 
                      region_name='ap-south-1')

            s3_object_key = self.conf['preprocessed']['preprocessed_df_path'] 
            s3.Object(self.conf['s3']['bucket_name'], s3_object_key).put(Body=csv_content)

            return {"df_push_status": 'success'}

    def _preprocess_data(self):
                
                spark = SparkSession.builder.appName("CSV Loading Example").getOrCreate()

                dbutils = DBUtils(spark)

                aws_access_key = dbutils.secrets.get(scope="secrets-scope", key="aws-access-key")
                aws_secret_key = dbutils.secrets.get(scope="secrets-scope", key="aws-secret-key")
                
                
                access_key = aws_access_key 
                secret_key = aws_secret_key

                print(f"Access key and secret key are {access_key} and {secret_key}")

                fs = feature_store.FeatureStoreClient()
                
                try:
                     inference_data_df = fs.read_table('default.xgboost-timeseries')
                     print("Feature is already present in the workspace")

                except:
                    s3 = boto3.resource("s3",aws_access_key_id=aws_access_key, 
                        aws_secret_access_key=aws_secret_key, 
                        region_name='ap-south-1')
                    
                    bucket_name =  self.conf['s3']['bucket_name']
                    csv_file_key = self.conf['s3']['file_path']

                    s3_object = s3.Object(bucket_name, csv_file_key)
                    
                    csv_content = s3_object.get()['Body'].read()

                    df_input = pd.read_csv(BytesIO(csv_content))

                    df_input = df_input.reset_index(drop=True)

                    df_input['Date'] = pd.to_datetime(df_input['Date'])
                    df_input['Date'] = df_input['Date'].apply(lambda x: x.replace(year = x.year + 5))

                    df_input = df_input.sort_values(by='Date',ascending=True)

                    # lis = list()
                    # for i in df_input['Order_Demand']:
                    #         lis.append(int(i.strip('()')))
                            
                    # df_input['Order_Demand'] = lis

                    df_input['Date']=pd.to_datetime(df_input['Date']).map(lambda x: x.strftime("%d-%m-%Y"))

                    df_input = df_input[['Date','Order_Demand']]

                    df_input['Date'] = pd.to_datetime(df_input['Date'])
                    
                    df_input = df_input.groupby(df_input['Date'].dt.strftime('%B %Y'))['Order_Demand'].sum().sort_values()

                    df_input = df_input.reset_index()

                    df_input['Date'] = pd.to_datetime(df_input['Date'])
                    df_input = df_input.sort_values(by='Date',ascending=True)

                    train_exog = ['Quarter', 'Week_Number','Month', 'Year', 'day', 'dayofyear', 'weekday',
                     'is_month_start', 'is_month_end','contri_week_quarter','SI_Quarter_week']
                    

                    df_input = df_input.rename(columns={'Date':'date','Order_Demand':'Sales'})

                    df1 = date_vars(df_input)

                    df = feature_engg(df1)

                    df = df.rename(columns={'Sales':'Order_Demand'})

                    df = df.reset_index(drop=True)
                   
                    #spark.sql(f"CREATE DATABASE IF NOT EXISTS {self.conf['feature-store']['table_name']}")
                    
                    table_name = self.conf['feature-store']['table_name']
                    print(table_name)

                   
                    df_spark = spark.createDataFrame(df)

                    

                    fs.create_table(
                            name=table_name,
                            primary_keys=[self.conf['feature-store']['lookup_key']],
                            df=df_spark,
                            schema=df_spark.schema,
                            description="timeseries features"
                        )
                    
                    print("Feature Store is created")

                    online_store_spec = AmazonDynamoDBSpec(
                            region="us-west-2",
                            write_secret_prefix="feature-store-example-write/dynamo",
                            read_secret_prefix="feature-store-example-read/dynamo",
                            table_name = self.conf['feature-store']['online_table_name']
                            )
                    
                    fs.publish_table(table_name, online_store_spec)

                            

    def launch(self):
         
         self._preprocess_data()

   

def entrypoint():  
    
    task = DataPreprocess()
    task.launch()


if __name__ == '__main__':
    entrypoint()