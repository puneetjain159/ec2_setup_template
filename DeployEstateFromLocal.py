import boto3
import json
import os
import sys
import time


TIMEOUT_MINS = 30

def get_config(config_file='config.json'):
    with open(config_file) as f:
        config = json.load(f)
    return config

def create_codezone(config):
    client_s3 = boto3.client("s3")
    project_name = config["Deployment"]["ProjectName"].lower()
    s3_str = "-".join([ project_name, 'codezone'])
    region = config["Deployment"]["Region"].lower()
    arn_iam = "arn:aws:iam::"
    arn_s3 = 'arn:aws:s3:::'
    aws_id = boto3.client('sts').get_caller_identity().get('Account')
    try:
        response = client_s3.create_bucket(
            ACL='private',
            Bucket=s3_str,
            CreateBucketConfiguration={
                'LocationConstraint': region
            }
        )
    except:
        print("Bucket" + s3_str + " already exists.")

    try:
        response_tag = client_s3.put_bucket_tagging(
            Bucket=s3_str,
            Tagging={
                'TagSet': [
                    {
                        "Key": "TechnicalLead",
                        "Value": config["Deployment"]["TechnicalLead"]
                    },
                    {
                        "Key": "DeploymentOwner",
                        "Value": config["Deployment"]["DeploymentOwner"]
                    },
                    {
                        "Key": "BillingLabel",
                        "Value": project_name
                    }
                ]
            }
        )
    except:
        print("Bucket " + s3_str + " already Updated")

def move_code_to_codezone(config):
    """
    Document important to call form right location.
    """
    client_s3 = boto3.client("s3")
    project_name = config["Deployment"]["ProjectName"].lower()
    s3_str = "-".join([project_name, 'codezone'])
    os.system("aws s3 cp --recursive ./ s3://" + s3_str  + "/")


def stack(config, stack_type, create_update):
    """
    This function creates or updates a stack for the GDLK
        project.
    Inputs
        config: a JSON file read in from local containing
            configuration settings for the deployment.
        stack_type: the type of stack to deploy, valid
            inputs are determined by a cloudformations tempalte
            existing a folder by the same name, e.g. for IDLK;
            DataStack, IngestionStack.
        create_update: flag to determine if the create_stack
            or update_stack method is used. e.g. CREATE or
            UPDATE.
    Outputs
        none
    """
    client_cf = boto3.client("cloudformation", region_name='ca-central-1')
    project_name = config["Deployment"]["ProjectName"].lower()
    stack_name = '-'.join([project_name, stack_type])
    deploy_template = config["Stacks"][stack_type]["DeployTemplate"]
    code_zone_loc =  project_name + '-codezone' 
    print("Code zone location: " + code_zone_loc)

    common_params = [
        {
            'ParameterKey': 'ProjectName',
            'ParameterValue': project_name
        },
        {
            'ParameterKey': 'VpcId',
            'ParameterValue': config["Deployment"]["VPC"]
        },
        {
            'ParameterKey': 'rEnvironmentName',
            'ParameterValue': config["Deployment"]["rEnvironmentName"]
        }
    ]

    tags = [
        {
            'Key': 'ProjectName',
            'Value': project_name
        },
        {
            'Key': 'VpcId',
            'Value': config["Deployment"]["VPC"]
        },
        {
            'Key': 'rEnvironmentName',
            'Value': config["Deployment"]["rEnvironmentName"]
        }
    ]
    if stack_type == "Ec2Stack":
        env = config["Stacks"][stack_type]["EnvironmentParameters"]
        params = [
            {
                'ParameterKey': 'SSHKeyName',
                'ParameterValue': env["EC2KeyName"]
            },
                        {
                'ParameterKey': 'Ec2Name',
                'ParameterValue': env["Ec2Name"]
            },
            {
                'ParameterKey': 'AvailabilityZones',
                'ParameterValue': env["AvailabilityZones"]
            },
            {
                'ParameterKey': 'InstanceType',
                'ParameterValue': env["InstanceType"]
            },            {
                'ParameterKey': 'AmiId',
                'ParameterValue': env["AmiId"]
            },            {
                'ParameterKey': 'SubnetId',
                'ParameterValue': env["SubnetId"]
            }

        ]
        params.extend(common_params)

    if create_update == "CREATE":
        try:
            print(f'https://{code_zone_loc}.s3.ca-central-1.amazonaws.com/{deploy_template}')
            response_create_stack = client_cf.create_stack(
                StackName=stack_name,
                TemplateURL=f'https://{code_zone_loc}.s3.ca-central-1.amazonaws.com/{deploy_template}',
                Parameters=params,
                Tags =tags,
                TimeoutInMinutes=TIMEOUT_MINS,
                Capabilities=['CAPABILITY_NAMED_IAM'],
                OnFailure='DELETE'
            )
            print("SUCCESS - " + stack_name + " Deployed")
        except BaseException as error:
            print("*** FAILURE - " + stack_name + " NOT deployed ***")
            print(error)
    else:
        try:
            response_update_stack = client_cf.update_stack(
                StackName=stack_name,
                TemplateURL='https://s3-eu-west-1.amazonaws.com/' + deploy_template_loc,
                Parameters=params,
                Capabilities=['CAPABILITY_NAMED_IAM']
            )
            print("SUCCESS - " + stack_name + " Deployed")
        except BaseException as error:
            print("*** FAILURE - " + stack_name + " NOT deployed ***")
            print(error)


def create_EMR_private_key(config, keypair_name, filepath):
    try:
        ec2 = boto3.client('ec2', region_name='ca-central-1')
        key = keypair_name
        SECRET_NAME = key
        keypair = ec2.create_key_pair(KeyName=key)
        print('Keypair {0} created successfully'.format(key))

        for key, value in keypair.items():
            if (key == 'KeyMaterial'):
                file_name = key
                pem_body = value

        try:
            assert (file_name =='KeyMaterial'),"This Secret does not contain a valid PEM file"

        except AssertionError as e:
            print("*********** ERROR - Please check that your Secret Name is referenced to a correct PEM file in Secrets Manager ***********")
            sys.exit(1)

        initial_path = os.getcwd() + "/PEM_KEYS"
        if not os.path.exists(initial_path):
            os.makedirs(initial_path)

        final_path = os.path.join(initial_path, file_name+".pem")
        pem_file= open(final_path, "w")
        pem_file.write(pem_body)
        pem_file.close()
        print("Your PEM file has been downloaded and stored in {0}".format(final_path))

    except Exception as e:
        print(e)
        print("Key Pair already exists")

    return key

def get_stack_status(config, stack_type, create_update):
    region = config['Deployment']['Region'].lower()
    client = boto3.client('cloudformation', region_name=region)
    project_name = config["Deployment"]["ProjectName"].lower()
    env = config["Deployment"]["rEnvironmentName"].lower()
    stack_name = '-'.join([ project_name, stack_type])
    print('**** Deployment Status for '+stack_name+' ****')
    while True:
        try:
            time.sleep(5)
            stack = client.describe_stacks(StackName=stack_name)['Stacks'][0]
            if stack['StackName'] == stack_name and \
                stack['StackStatus'] == "CREATE_COMPLETE" and \
                stack['StackId'] == (stack['StackId']):
                print('Stack Status : ' + stack['StackStatus'])
                return stack['StackStatus']
                break
            elif stack['StackStatus'] == "UPDATE_COMPLETE" and \
                 stack['StackId'] == (stack['StackId']):
                print('Stack Status : ' + stack['StackStatus'])
                return stack['StackStatus']
                break
            elif stack['StackStatus'] == "ROLLBACK_COMPLETE" and \
                stack['StackId'] == (stack['StackId']):
                print('Stack Status : ' + stack['StackStatus'])
                return stack['StackStatus']
                break
            elif stack['StackStatus'] == "UPDATE_ROLLBACK_COMPLETE" and \
                stack['StackId'] == (stack['StackId']):
                print('Stack Status : ' + stack['StackStatus'])
                return stack['StackStatus']
                break
            elif stack['StackStatus'] == "DELETE_COMPLETE" and \
                stack['StackId'] == (stack['StackId']):
                print('Stack Status : ' + stack['StackStatus'])
                return stack['StackStatus']
                break
            elif stack['StackStatus'] == "DELETE_FAILED" and \
                stack['StackId'] == (stack['StackId']):
                print('Stack Status : ' + stack['StackStatus'])
                return stack['StackStatus']
                break
            else:
                print('-----'+stack['StackName']+'-----')
                print('Stack Status : ' + stack['StackStatus'])
                continue
        except:
            print('Stack Status : '+stack_name+' : ' +
                  ' Stack Not Deployed : Check CloudFormationStack in AWS Console for Error')
            return 'StackNotDeployed'


if __name__ == '__main__':
    config = get_config()

    CREATE_EC2_STACK = config["Stacks"]["Ec2Stack"]["CREATE_STACK"]
    UPDATE_EC2_STACK = config["Stacks"]["Ec2Stack"]["UPDATE_STACK"]

    create_codezone(config)
    move_code_to_codezone(config)
    if CREATE_EC2_STACK:
        keypair_name = config['Stacks']['Ec2Stack']['EnvironmentParameters']['EC2KeyName']
        key = create_EMR_private_key(config, keypair_name, "./Ec2Stack")
        stack(config, 'Ec2Stack', "CREATE")
        status = get_stack_status(config, 'Ec2Stack', "CREATE")
    if UPDATE_EC2_STACK:
        stack(config, 'Ec2Stack', "UPDATE")
        status = get_stack_status(config, 'Ec2Stack', "UPDATE")
