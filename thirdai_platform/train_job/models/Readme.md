# Models

This directory contains the implementation of various machine learning models using ThirdAI's Models.


### Model Interface

#### Abstract Base Class: `Model`

The `Model` class is an abstract base class that defines the following methods:
- `__init__()`: Initializes the model with general and training variables, sets up directories, and a reporter for status updates.
- `train(self, **kwargs)`: Abstract method for training the model.
- `evaluate(self, **kwargs)`: Abstract method for evaluating the model.

### Concrete Implementations

#### `NDBModel`

An extension of the `Model` class that integrates with ThirdAI's NeuralDB. It provides methods to:
- Train with unsupervised and supervised data.
- Load and save NeuralDB instances.
- Handle shard data and supervised files.

#### `SingleMach`

An extension of `NDBModel` designed for single Mach model training. It includes:
- Initialization of the Mach model with specific parameters.
- Methods for training and evaluation.

#### `FinetunableRetriever`

An extension of `NDBModel` for finetunable retriever models. It includes:
- Initialization of the NeuralDB with a retriever.
- Methods for training and evaluation.

#### `MultipleMach`

An extension of `NDBModel` that supports multiple models within a shard. It includes:
- Initialization and loading of multiple Mach models.
- Methods for sharding data and supervised training.

#### `ShardMach`

An extension of `NDBModel` that handles sharded training with Mach models. It includes:
- Methods to get and train on shard data.
- Evaluation and saving of shard models.
