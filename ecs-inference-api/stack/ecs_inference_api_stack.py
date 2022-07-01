from aws_cdk import aws_apigatewayv2 as api_gw
from aws_cdk import aws_apigatewayv2_integrations as integrations
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_elasticloadbalancingv2 as elb
from aws_cdk import core


class EcsInferenceApiStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # ====================================
        # Amazn ECR
        # ====================================
        ## Create new Container Image.
        # ecr_image = aws_lambda.EcrImageCode.from_asset_image(directory=os.path.join("./", "lambda-image"))

        # ====================================
        # Amazon VPC
        # ====================================
        vpc = ec2.Vpc(self, "MyVpc", max_azs=2)
        # Use one subnet per availability zone
        subnet_selection = ec2.SubnetSelection(one_per_az=True)

        # ====================================
        # Amazon ALB
        # ====================================
        load_balancer_security_group = ec2.SecurityGroup(
            self,
            "LoadBalancerSG",
            vpc=vpc,
            description="LoadBalancer Security Group",
            security_group_name="LoadBalancer-SecurityGroup",
        )

        load_balancer_security_group.add_ingress_rule(
            connection=ec2.Port.tcp(80),
            peer=ec2.Peer.any_ipv4(),
            description="Allow from anyone on port 80",
        )

        application_load_balancer = elb.ApplicationLoadBalancer(
            self,
            "ECSApplicationLoadBalancer",
            security_group=load_balancer_security_group,
            vpc=vpc,
            vpc_subnets=subnet_selection,
        )

        target_group = elb.ApplicationTargetGroup(
            self,
            "LoadBalancerListenerTargetGroupECS",
            target_type=elb.TargetType.IP,
            protocol=elb.ApplicationProtocol.HTTP,
            port=80,
            vpc=vpc,
            target_group_name="LBListenerTargetGroupECS",
        )

        application_load_balancer_listener = elb.ApplicationListener(
            self,
            "ECSApplicationListener",
            load_balancer=application_load_balancer,
            protocol=elb.ApplicationProtocol.HTTP,
            port=80,
            default_action=elb.ListenerAction.forward(
                target_groups=[target_group]
            ),
        )

        vpc_link = api_gw.VpcLink(
            self,
            "APIGWVpcLinkToPrivateHTTPEndpoint",
            vpc=vpc,
            subnets=subnet_selection,
            vpc_link_name="APIGWVpcLinkToPrivateHTTPEndpoint",
        )

        # ====================================
        # Amazon API Gateway
        # ====================================

        read_api = api_gw.HttpApi(self, "Read-API", api_name="Read-API")

        read_api_gateway_integration = integrations.HttpAlbIntegration(
            listener=application_load_balancer_listener,
            method=api_gw.HttpMethod.ANY,
            vpc_link=vpc_link,
        )

        read_api_gateway_route = api_gw.HttpRoute(
            self,
            "ReadApiGatewayRoute",
            http_api=read_api,
            route_key=api_gw.HttpRouteKey.with_(path="/{proxy+}"),
            integration=read_api_gateway_integration,
        )

        # ====================================
        # Amazon ECS
        # ====================================
        cluster = ecs.Cluster(self, "Ec2Cluster", vpc=vpc)

        asg = autoscaling.AutoScalingGroup(
            self,
            "DefaultAutoScalingGroup",
            instance_type=ec2.InstanceType("t2.micro"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2(),
            vpc=vpc,
        )
        capacity_provider = ecs.AsgCapacityProvider(
            self, "AsgCapacityProvider", auto_scaling_group=asg
        )
        cluster.add_asg_capacity_provider(capacity_provider)

        # Create EC2 Task Definition
        # https://docs.aws.amazon.com/cdk/api/v1/python/aws_cdk.aws_ecs/Ec2TaskDefinition.html
        task_definition = ecs.Ec2TaskDefinition(stack, "TaskDef")

        container = task_definition.add_container(
            id="container",
            image=ecs.ContainerImage.from_registry("amazon/amazon-ecs-sample"),
            gpu_count=2,
        )
        port_mapping = ecs.PortMapping(
            container_port=80, host_port=8080, protocol=ecs.Protocol.TCP
        )
        container.add_port_mappings(port_mapping)

        # Create Service
        service = ecs.Ec2Service(
            stack, "Service", cluster=cluster, task_definition=task_definition
        )

        # ====================================
        # Connect ECS and ALB
        # ====================================
        ecs_security_group_ingress = ec2.CfnSecurityGroupIngress(
            self,
            "ECSSecurityGroupIngress",
            from_port=80,
            to_port=80,
            group_id=ecs_security_group.security_group_id,
            source_security_group_id=load_balancer_security_group.security_group_id,
            ip_protocol="tcp",
        )

        load_balancer_security_group_egress = ec2.CfnSecurityGroupEgress(
            self,
            "LoadBalancerSecurityGroupEgress",
            from_port=80,
            to_port=80,
            group_id=load_balancer_security_group.security_group_id,
            destination_security_group_id=ecs_security_group.security_group_id,
            ip_protocol="tcp",
        )

        # Connect the exposed port on your container to the ALB
        target_group.add_target(
            ecs_service.load_balancer_target(
                container_name="nginx", container_port=80
            )
        )
