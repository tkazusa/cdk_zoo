#!/usr/bin/env python3
import aws_cdk as cdk

from lambda_ec2_run_terminate.lambda_ec2_run_terminate_stack import \
    LambdaEC2RunTerminateStack

app = cdk.App()
AisinDriverMonitoringStack(app, "AisinDriverMonitoringStack")
app.synth()
