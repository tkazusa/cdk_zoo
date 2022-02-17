import json
import os

import boto3

REGION = os.environ['REGION']
IMAGE_ID = os.environ['IMAGE_ID']
TABLE_NAME = os.environ['TABLE_NAME']

# AWS サービスの API を叩くためのクライアント
ec2 = boto3.client('ec2', region_name=REGION)
dynamodb = boto3.resource('dynamodb')
s3 = boto3.resource('s3')

# 書き込み対象となる DynamoDB のテーブル
table = dynamodb.Table(TABLE_NAME)

def fetch_ovject_in_s3bucket(event):
    """ S3 にアプロードされたファイルを読み込む """
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    bucket = s3.Bucket(bucket_name)
    key = event['Records'][0]['s3']['object']['key']
    obj = bucket.Object(key).get()
    return obj


def lambda_handler(event, context):
    # 設定ファイルを S3 から取得
    obj = fetch_ovject_in_s3bucket(event)
    body = obj['Body'].read()
    # 取得したファイルの中身を読み取る
    settings = json.loads(body.decode('utf-8'))
    print(f'Processing setting is {settings}')

    # DynamoDB は動画ファイル数が1単位
    # ファイル数に応じてインスタンスを立て、DynamoDB へその情報を書き込む
    for setting in settings["settings"]:
        shot_id = setting['ShotID']
        response = ec2.run_instances(
            ImageId=IMAGE_ID,
            MaxCount=1,
            MinCount=1,
            InstanceType='t2.micro'
        )

        instance = response["Instances"][0]
        
        # finename 毎に DynamoDB にタスク情報を保存
        filenames = setting['filenames']
        for filename in filenames:
            response = table.put_item(
                Item={
                    'ShotID': shot_id,
                    'InstanseID': str(instance['InstanceId'],
                    'FileID': filename)
                }
            )
            print(f"PutItem Succeeded, ShotID: {shot_id}, InstanceID: {instance['InstanceId']}, FileID: {filename}")

    return {
        'statusCode': 200,
        'body': {"settings": settings, "InstanceID": instance['InstanceId']}
        }
