from client.bazaar import ModelBazaar
from client.clients import Login, Model

base_url = "http://52.53.207.253/api/"
admin_client = ModelBazaar(base_url)
admin_client.log_in("gautam@thirdai.com", "password")

model_name = "pubmed"

model = admin_client.train(
    model_name,
    unsupervised_docs=["s3://novatris-demo/pubmed_1M.csv"],
    model_options={"on_disk": False},
    supervised_docs=[],
    doc_type="s3",
    doc_options={
        "/Users/gautamsharma/Downloads/pubmed_1M.csv": {
            "csv_strong_columns": ["TITLE"],
            "csv_weak_columns": ["TEXT"],
        }
    },
)
admin_client.await_train(model)
