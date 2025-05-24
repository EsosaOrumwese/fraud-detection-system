import boto3  # type: ignore

SAGEMAKER = boto3.client("sagemaker")


def handler(event, context):
    # Stop active SageMaker endpoints
    for ep in SAGEMAKER.list_endpoints(StatusEquals="InService")["Endpoints"]:
        name = ep["EndpointName"]
        print(f"Stopping endpoint {name}")
        SAGEMAKER.stop_endpoint(EndpointName=name)

    # Stop notebook instances
    for nb in SAGEMAKER.list_notebook_instances(StatusEquals="InService")[
        "NotebookInstances"
    ]:
        name = nb["NotebookInstanceName"]
        print(f"Stopping notebook {name}")
        SAGEMAKER.stop_notebook_instance(NotebookInstanceName=name)

    return {"status": "stopped"}
