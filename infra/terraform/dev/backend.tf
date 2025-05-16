# A shared, versioned state is expected not local .tfstate files
#
terraform {
  backend "s3" {
    bucket         = "fraud-tfstate-dev" # create once, keep private+encrypted
    key            = "terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "fraud-tfstate-lock" # <- DynamoDB table with "LockID" hash key
    encrypt        = true
  }
}
