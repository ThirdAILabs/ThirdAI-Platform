from client.bazaar import ModelBazaar
from client.clients import Login, Model

base_url = "http://52.53.207.253/api/"
admin_client = ModelBazaar(base_url)
admin_client.log_in("gautam@thirdai.com", "password")

model_name = "IntuitModel_1"

model = admin_client.train(
    model_name,
    unsupervised_docs=["s3://novatris-demo/combined_intuit.csv"],
    model_options={"ndb_options": {"ndb_sub_type": "v2"}, "on_disk": False},
    supervised_docs=[],
    doc_type="s3",
    doc_options={
        "/Users/pratikqpranav/ThirdAI/Tests/combined_intuit.csv": {
            "csv_metadata_columns": {
                "docId": "string",
                "instruction": "string",
                "filePath": "string",
                "createdTime": "string",
                "Tax Year": "string",
                "Formset": "string",
                "Form Id": "string",
                "Form Field Id": "string",
                "LLM Form Description": "string",
                "LLM Field Description": "string",
                "Field Type": "string",
                "Array": "string",
                "Field Name": "string",
                "Min": "string",
                "Field FullName": "string",
                "Source PT Form": "string",
                "Field Description": "string",
                "SNo": "string",
                "Field ID": "string",
                "CID FormID": "string",
                "Table Id": "string",
                "Export": "string",
                "Max": "string",
                "Link Form": "string",
                "Picklist": "string",
                "Link Field ID": "string",
                "CID TableID": "string",
                "CID FieldID": "string",
            },
            "csv_strong_columns": [
                "Field FullName",
                "Field Description",
                "LLM Form Description",
                "LLM Field Description",
            ],
        }
    },
)
admin_client.await_train(model)
