import json
import os

import boto3
from botocore.exceptions import ClientError

REGION = os.environ['REGION']
TABLE_NAME = os.environ['TABLE_NAME']

# AWS サービスの API を叩くためのクライアント
ec2 = boto3.client('ec2', region_name=REGION)
dynamodb = boto3.resource('dynamodb')
s3 = boto3.resource('s3')

# 読み込み対象となる DynamoDB のテーブル
table = dynamodb.Table(TABLE_NAME)

def fetch_ovject_in_s3bucket(event):
    """ S3 にアプロードされたファイルを読み込む """
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    bucket = s3.Bucket(bucket_name)
    key = event['Records'][0]['s3']['object']['key']
    obj = bucket.Object(key).get()
    return obj


# main となる関数
def lambda_handler(event, context):
    # 設定ファイルを S3 から取得
    obj = fetch_ovject_in_s3bucket(event)
    body = obj['Body'].read()
    # 取得したファイルの中身を読み取る
    output = json.loads(body.decode('utf-8'))
    print(f'Output file is {output}')

    try:
        # DynamoDB から、output.json に記載されていた EC2 インスタンスの ID を取得
        ddb_response = table.get_item(Key ={'file_id': output['filename']})
        instance_id = ddb_response['Item']['instance_id']
        
        # 該当した EC2 インスタンスを terminate
        ec2_response = ec2.terminate_instances(
            InstanceIds=[str(instance_id)]
        )
        print(f"Terminate Succeeded, Instance ID: {instance_id}")

    except ClientError as e:
        print(e.response['Error']['Message'])

    return {
        'statusCode': 200,
        'body': event
        }
