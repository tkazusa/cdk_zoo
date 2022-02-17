import os.path
from os import environ
from typing import _SpecialForm

from aws_cdk import Stack  # Duration,; aws_sqs as sqs,
from aws_cdk import App, Aws, CfnOutput
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications
from aws_cdk import aws_s3objectlambda as s3_object_lambda
from aws_cdk.aws_s3_assets import Asset
from constructs import Construct

dirname = os.path.dirname(__file__)
IMAGE_ID = "ami-0c19f80dba70861db"
REGION = "us-east-1"


class LambdaEC2RunTerminateStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # --- S3 Bucket ---
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_s3/Bucket.html
        bucket = s3.Bucket(scope=self, id="S3 bucket")
        #   access_control=s3.BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
        #   encryption=s3.BucketEncryption.S3_MANAGED,
        #   block_public_access=s3.BlockPublicAccess.BLOCK_ALL
        # )
        # アクセスコントロールを、このアカウントのリソースからに制限
        # https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-policies.html
        # S3_policy_conditions = {
        #    "StringEquals": {"s3:DataAccessPointAccount": f"{Aws.ACCOUNT_ID}"}
        # }
        # S3 Bucket にポリシーを付与
        # bucket.add_to_resource_policy(
        #    iam.PolicyStatement(
        #         actions=["*"],
        #         principals=[iam.AnyPrincipal()],
        #         resources=[bucket.bucket_arn, bucket.arn_for_objects('*')],
        #         conditions=S3_policy_conditions
        #     )
        # )

        # UserData 用の Script を Asset として S3 に保存
        script = Asset(self, "Asset", path=os.path.join(dirname, "assets/configure.sh"))

        # --- AWS Lambda ---
        # https://github.com/aws-samples/aws-cdk-examples/blob/master/python/lambda-s3-trigger/s3trigger/s3trigger_stack.py
        # EC2 起動用の AWS Lambda を作成
        # --- Lambda 用の IAM Role ---
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/Role.html
        lambda_role = iam.Role(
            scope=self,
            id="lambda_role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        # --- Policy Statements ---
        # CDK での IAM ポリシーステートメントの設定参考
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/PolicyStatement.html
        policy_statement_logs = iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            effect=iam.Effect.ALLOW,
            resources=["arn:aws:logs:*:*:*"],
        )

        policy_statement_ec2 = iam.PolicyStatement(
            actions=["ec2:Start*", "ec2:Stop*", "ec2:Run*", "ec2:Terminate*"], effect=iam.Effect.ALLOW, resources=["*"]
        )

        policy_statement_s3 = iam.PolicyStatement(
            actions=["s3:*Object"], effect=iam.Effect.ALLOW, resources=[f"arn:aws:s3:::{bucket.bucket_name}/*"]
        )

        # --- Policy for Lambda Role
        # CDK での IAM ポリシー設定参考
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_iam/Policy.html
        lambda_policy = iam.Policy(
            scope=self,
            id="lambda_policy",
            statements=[policy_statement_logs, policy_statement_ec2, policy_statement_s3],
            roles=[lambda_role],
        )

        # --- AWS Lambda Function for Run
        run_function = _lambda.Function(
            scope=self,
            id="run_function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./aisin_driver_monitoring/lambdafn/run_function"),
            handler="lambda_handler.lambda_handler",
            environment={"IMAGE_ID": IMAGE_ID, "REGION": REGION},
            role=lambda_role,
        )

        # 通知イベントの通知先を AWS Lambda に設定
        # https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_s3/EventType.html
        run_notification = aws_s3_notifications.LambdaDestination(run_function)
        input_filter = s3.NotificationKeyFilter(prefix="input/")
        bucket.add_event_notification(s3.EventType.OBJECT_CREATED, run_notification, *[input_filter])

        # --- AWS Lambda Function for terminate
        terminate_function = _lambda.Function(
            scope=self,
            id="terminate_function",
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset("./aisin_driver_monitoring/lambdafn/terminate_function"),
            handler="lambda_handler.lambda_handler",
            environment={"REGION": REGION},
            role=lambda_role,
        )

        # 通知イベントの通知先を AWS Lambda に設定
        terminate_notification = aws_s3_notifications.LambdaDestination(terminate_function)
        output_filter = s3.NotificationKeyFilter(prefix="output/")
        bucket.add_event_notification(s3.EventType.OBJECT_CREATED, terminate_notification, *[output_filter])

        # --- DynamoDB ---
        # https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_dynamodb.html
        # https://github.com/aws-samples/aws-cdk-examples/blob/master/python/dynamodb-lambda/dynamodb_lambda/dynamodb_lambda_stack.py
        dynamodb_table = ddb.Table(
            scope=self, id="dynamodb_table", partition_key=ddb.Attribute(name="ShotID", type=ddb.AttributeType.STRING)
        )
        run_function.add_environment("TABLE_NAME", dynamodb_table.table_name)
        dynamodb_table.grant_read_write_data(run_function)

        terminate_function.add_environment("TABLE_NAME", dynamodb_table.table_name)
        dynamodb_table.grant_read_write_data(terminate_function)
