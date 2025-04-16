import boto3
import json
import os
from datetime import datetime, timedelta, timezone

def lambda_handler(event, context):
    current_time = datetime.now(tz=timezone(timedelta(hours=8)))
    
    process_ec2_instances(current_time)
    process_eks_clusters(current_time)
    process_rds_instances(current_time)
    process_lifecycle_policy_for_all_repos()

    return {
        'statusCode': 200,
        'body': 'AWS resources monitoring, stopping, and deletion completed'
    }

def process_ec2_instances(current_time):
    ec2 = boto3.client('ec2')
    
    print("debug-> To get all EC2 instances")
    instances = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
    ])

    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            instance_id = instance['InstanceId']
            state = instance['State']['Name']
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}

            print(f"debug-> Processing instance ID: {instance_id}, State: {state} at {current_time}")

            # Check if the instance should be retained
            retain_instance = tags.get('Keep', '').lower() == 'true'

            if state == 'running':
                # Check if it's past 19:00 CST
                if current_time.hour >= 19:
                    print(f"Stopping instance {instance_id} as it's past 19:00 CST")
                    ec2.stop_instances(InstanceIds=[instance_id])
                    
                    # Add a tag to record when the instance was stopped
                    ec2.create_tags(
                        Resources=[instance_id],
                        Tags=[{'Key': 'StoppedTime', 'Value': current_time.isoformat()}]
                    )
            
            elif state == 'stopped' and not retain_instance:
                # Check if the instance has been stopped for more than 3 days
                stopped_time_str = tags.get('StoppedTime')
                
                if stopped_time_str:
                    stopped_time = datetime.fromisoformat(stopped_time_str)
                    if (current_time - stopped_time) > timedelta(days=3):
                        print(f"Terminating instance {instance_id} as it has been stopped for more than 3 days")
                        ec2.terminate_instances(InstanceIds=[instance_id])
            
            elif state == 'stopped' and retain_instance:
                print(f"Instance {instance_id} is retained despite being stopped for a long time")

def process_eks_clusters(current_time):
    eks = boto3.client('eks')
    
    print("debug-> To get all EKS clusters")
    clusters = eks.list_clusters()['clusters']

    for cluster_name in clusters:
        cluster = eks.describe_cluster(name=cluster_name)['cluster']
        status = cluster['status']
        tags = cluster.get('tags', {})

        print(f"debug-> Processing EKS cluster: {cluster_name}, Status: {status} at {current_time}")

        retain_cluster = tags.get('Keep', '').lower() == 'true'

        if status == 'ACTIVE':
            if current_time.hour >= 19:
                if not retain_cluster:
                    print(f"Stopping EKS cluster {cluster_name} as it's past 19:00 CST")
                    # Note: EKS clusters can't be "stopped", but we can delete them
                    eks.delete_cluster(name=cluster_name)

def process_rds_instances(current_time):
    rds = boto3.client('rds')
    
    print("debug-> To get all RDS instances")
    instances = rds.describe_db_instances()['DBInstances']

    for instance in instances:
        instance_id = instance['DBInstanceIdentifier']
        status = instance['DBInstanceStatus']
        tags = {tag['Key']: tag['Value'] for tag in rds.list_tags_for_resource(ResourceName=instance['DBInstanceArn'])['TagList']}

        print(f"debug-> Processing RDS instance: {instance_id}, Status: {status} at {current_time}")

        retain_instance = tags.get('Keep', '').lower() == 'true'

        if status == 'available':
            if current_time.hour >= 19:
                print(f"Stopping RDS instance {instance_id} as it's past 19:00 CST")
                rds.stop_db_instance(DBInstanceIdentifier=instance_id)
        elif status == 'stopped' and not retain_instance:
            # Check if the instance has been stopped for more than 3 days
            stopped_time_str = tags.get('StoppedTime')
            if stopped_time_str:
                stopped_time = datetime.fromisoformat(stopped_time_str)
                if (current_time - stopped_time) > timedelta(days=3):
                    print(f"Deleting RDS instance {instance_id} as it has been stopped for more than 3 days")
                    rds.delete_db_instance(DBInstanceIdentifier=instance_id, SkipFinalSnapshot=True)

def process_lifecycle_policy_for_all_repos(): 
    # Define lifecycle for all images in the ECR
    lifecycle_policy = {
    "rules": [
        {
            "rulePriority": 1,
            "description": "Delete images out of 7 days",
            "selection": {
                "tagStatus": "any",
                "countType": "sinceImagePushed",
                "countUnit": "days",
                "countNumber": 7
            },
            "action": {
                "type": "expire"
            }
        }
            ]
    }
    # Fetch all repos in the ECR
    ecr_client = boto3.client('ecr')

    print("debug-> To get all repos in ECR")
    response = ecr_client.describe_repositories()
    repositories = response['repositories']
    
    # Apply lifecycle on all repos
    for repo in repositories:
        repo_name = repo['repositoryName']
        ecr_client.put_lifecycle_policy(
                repositoryName=repo_name,
                lifecyclePolicyText=json.dumps(lifecycle_policy)
            )