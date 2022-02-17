import aws_cdk as core
import aws_cdk.assertions as assertions

from aisin_driver_monitoring.aisin_driver_monitoring_stack import AisinDriverMonitoringStack

# example tests. To run these tests, uncomment this file along with the example
# resource in aisin_driver_monitoring/aisin_driver_monitoring_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = AisinDriverMonitoringStack(app, "aisin-driver-monitoring")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
