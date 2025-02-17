from .models import *
from scipy import stats

from random import randint
import sklearn
import pandas as pd
import numpy as np
import argparse
from tensorboard.summary import Writer
from abc import ABCMeta, abstractmethod, abstractstaticmethod
import random

from lifelines.utils import concordance_index

## FIXME:: modularize these imports and remove as many as possible!

from sklearn.model_selection import train_test_split

import torch
import torch.utils.data

import pytorch_lightning as pl
from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import EarlyStopping
from pytorch_lightning.callbacks import ModelCheckpoint

from sklearn.model_selection import StratifiedKFold
import seaborn as sns

def abstractattr(f):
    return property(abstractmethod(f))

# TODO: Figure out what the abc stuff is up to
# TODO: Make it so that there is a parameter (tuple) called hidden_dims 
# TODO: Reference LassoNet to see other parameters I could take in
# TODO; Make documentation 
# TODO: Figure out where type validation is done. There is no "set_params" in lassoNET
class BaseCINET(sklearn.base.BaseEstimator, metaclass=ABCMeta):
    def __init__(self,
    *, 
    modelPath='',
    batch_size=256,
    num_workers=8,
    folds=5, 
    use_folds=True, 
    momentum=5.0, 
    weight_decay=5.0, 
    sc_milestones=[1,2,5,15,30], 
    sc_gamma=0.35,
    delta=0.0, 
    dropout=0.4, 
    learning_rate=0.01, 
    device='cpu',
    max_epochs=12,
    seed=420):
        """Initialize the CINET sklearn class

        All relevant variables can be initialized here. Of interest are 'delta' 'batch_size' 'modelPath' and 'device'.

        Parameters
        ----------
        modelPath : str
            This it the path to where your model can be saved after training. The model will also load the model at this path when making predictions.
            Empty by default.
        batch_size : int
            Batch size when training.
            Set to 256 by default.
        num_workers : int
            Number of sub-processes to use for dataloading in under-the-hood PyTorch model.
            Set to 8 by deafult.
        folds : int
            Number of cross-validation folds.
            Set to 5 by default.
        use_folds : bool
            Value set to determine if folds should be used.
            Set to false by default.
        momentum : float
            Momentum to be used in neural network training. 
            Set to 5.0 by default.
        weight_decay : float 
            Weight decay to be used in neural network training. 
            Set to 5.0 by default.
        sc_milestones : array
            Milestones for optimization / learning rate scheduler. Array of integers.
            Set to [1,2,5,15,30] by default.
        sc_gamma : float
            Gamma value for optimization / learning rate scheduler. 
            Set to 0.35 by default. 
        delta : float
            The minimum difference between target/response (y-vector) values for training data pairs to be included in training the siamese network.
            Set to 0.0 by default. 
        dropout : float
            Dropout value used in neural network training. 
            Set to 0.4 by default. 
        learning_rate : float
            Default learning rate to be used in neural network training. 
            Set to 0.01 by default. 
        device : string
            The device to train on. Can be 'cpu' or 'gpu'.
            Set to 'cpu' by default.
        seed : int
            The seed value for neural network training. 
            Set to 420 by default.

        Examples
        --------
        >>> model = deepCINET(batch_size=1024, momentum=4.0, delta=0.05, seed=999)
        >>> model = ECINET(batch_size=1024, momentum=4.0, delta=0.05, seed=999)        
        """

        self.arg_lists = []
        self._estimator_type = 'classifier'
        self.modelPath = modelPath
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.folds = folds
        self.use_folds = use_folds
        self.momentum = momentum
        self.weight_decay = weight_decay
        self.sc_milestones = sc_milestones
        self.sc_gamma = sc_gamma
        self.delta = delta
        self.dropout = dropout
        self.learning_rate = learning_rate
        self.device = device
        self.max_epochs = max_epochs
        self.seed = seed


    def _validate_params(self): 
        """Validate all parameters initialized in the model. 
        This function is a private function called every time that .fit() is called. 
        """
        assert isinstance(self.batch_size, int), 'batch_size must be of type int'
        assert isinstance(self.num_workers, int), 'num_workers must be of type int'
        assert isinstance(self.folds, int), 'folds must be of type int'
        assert isinstance(self.use_folds, bool), 'use_folds must be of type bool'
        assert isinstance(self.momentum, float), 'momentum must be of type float'
        assert isinstance(self.weight_decay, float), 'weight_decay must be of type float'
        assert isinstance(self.sc_milestones, list), 'sc_milestones must be of type list'
        assert isinstance(self.sc_gamma, float), 'sc_gamma must be of type float'
        assert isinstance(self.delta, float), 'delta must be of type float'
        assert isinstance(self.dropout, float), 'dropout must be of type float'
        assert isinstance(self.learning_rate, float), 'learning_rate must be of type float'
        assert isinstance(self.device, str), 'device must be of type str'
        assert (self.device in ['cpu', 'gpu']), 'device must be either "cpu" or "gpu"'
        assert isinstance(self.seed, int), 'seed must be of type int'


    def fit(self, X=None, y=None, cross_validation=True, random_pairs=False): 
        """Train the model based on training input data 
        
        Parameters
        ----------
        X : pandas.dataframe
            Input training data.
        y : pandas.dataframe
            Output data to be predicted.
        """
        self._validate_params()
        print("🚀🚀🚀🚀TESTING WITH HYPERPARAMETERS🚀🚀🚀🚀")
        print("delta", self.delta)

        self.hyperparams = {
            "num_workers": self.num_workers, 
            "batch_size" : self.batch_size, 
            "folds" : self.folds, 
            "accumulate_grad_batches": 1, 
            "min_epochs": 0, 
            "min_steps" : None,
            "max_epochs" : self.max_epochs, 
            "max_steps" : None, 
            "check_val_every_n_epoch" : 1, 
            "gpus" : 0,
            "overfit_pct" : 0,
            "seed" : self.seed,
            "sc_milestones" : self.sc_milestones,
            "sc_gamma" : self.sc_gamma,
            "device" : self.device,
        }

        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        np.random.seed(self.hyperparams["seed"])
        torch.manual_seed(self.hyperparams["seed"])

        self.config = self.getConfig()

        # Check if both data have same # of rows 
        if len(X) != len(y):
            raise Exception("X and y values are not of the same length")
        
        self.config['dat_size'] = X.shape[1]
        self.config['dropout'] = self.dropout
        self.config['lr'] = self.learning_rate

        combined_df = pd.concat([X, y], axis=1)
        combined_df.columns.values[-1] = 'target'

        # Check if the combined dataframe is the right size
        if len(combined_df) != len(X): 
            raise Exception("X and y values must have the same indices")
        loaders = self.get_dataloaders(combined_df, cross_validation, random_pairs)

        # TODO: Remove this? Hard-coded stuff here. 
        # filename_log = f'Vorinostat-delta={self.delta:.3f}'
        # checkpoint_callback = ModelCheckpoint(
        #     monitor='val_ci',
        #     dirpath='./Saved_models/DeepCINET/rnaseq/',
        #     filename=filename_log,
        #     save_top_k=1,
        #     mode='max'
        # )
        self.hyperparams["folds"] = 1
        # overfit_pct=hparams.overfit_pct)
        if cross_validation:
            num_rounds = 1
            cross_val_ci_per_round = []
            for _ in range(num_rounds):
                global_prediction = pd.DataFrame()
                for (train_dl, val_dl, val_dataset) in loaders:
                    self.siamese_model = self.get_model(self.config)
                    trainer = self.get_trainer(self.hyperparams)
                    trainer.fit(self.siamese_model, train_dl)
                    predictions = self.predict(val_dataset)
                    global_prediction = pd.concat([global_prediction, predictions])
                    global_prediction = global_prediction.sort_index(axis=0)
                val_ci = concordance_index(y.iloc[:,0].tolist(), global_prediction.iloc[:,0].tolist())
                cross_val_ci_per_round.append(val_ci)
        else:
            if random_pairs:
                valid_dl, random_dl, val_dataset = loaders[0]
                self.siamese_model = self.get_model(self.config)
                trainer = self.get_trainer(self.hyperparams)
                trainer.fit(self.siamese_model, valid_dl)
                y_val = val_dataset['target']
                valid_predictions = self.predict(val_dataset.drop('target', axis=1))

                self.siamese_model = self.get_model(self.config)
                trainer = self.get_trainer(self.hyperparams)
                trainer.fit(self.siamese_model, random_dl)
                random_predictions = self.predict(val_dataset.drop('target', axis=1))

                valid_score = concordance_index(y_val.tolist(), valid_predictions.tolist())
                random_score = concordance_index(y_val.tolist(), random_predictions.tolist())
                cross_val_ci_per_round = (valid_score, random_score)
            else:
                train_dl, _, _ = loaders[0]
                self.siamese_model = self.get_model(self.config)
                trainer = self.get_trainer(self.hyperparams)
                if train_dl is not None:
                    trainer.fit(self.siamese_model, train_dl)
                    cross_val_ci_per_round = -1
                    if self.modelPath != '': 
                        torch.save(self.siamese_model, self.modelPath)
                else:
                    cross_val_ci_per_round = -2
        return cross_val_ci_per_round

    def predict(self, X):
        """Predict a ranked list from input data
        
        Parameters
        ----------
        X : pandas.dataframe
            Input test data.

        Returns
        -------
        torch.Tensor
            Returns a pytorch tensor of the predicted values

        """

        # Non-official way to do this
        # np.random.seed(self.hyperparams["seed"])
        # torch.manual_seed(self.hyperparams["seed"])
        
        index = X.index.values.tolist()
        X = torch.FloatTensor(X.values)
        if self.modelPath != '': 
            self.siamese_model = torch.load(self.modelPath)

        self.siamese_model.eval()
        
        result_df = pd.Series(torch.squeeze(self.siamese_model.fc(X).detach()).numpy().tolist(), index=index)
        return result_df

    def score(self, X=None, y=None):
        temp_list = self.predict(X).tolist()
        final_list = []
        for t in temp_list: 
            final_list.append(t[0])

        # return stats.spearmanr(y,final_list)
        return concordance_index(y,final_list)

    # HELPER SUB-CLASSES AND SUB-FUNCTIONS

    def add_argument_group(self, name):
        arg = self.parser.add_argument_group(name)
        self.arg_lists.append(arg)
        return arg
    
    # DEBUG TOOLS 
    
    def getPytorchModel(self):
        return self.siamese_model if self.siamese_model is not None else None

    ### TO BE IMPLEMENTED BY INHERITING CLASSES ###

    @abstractattr
    def getConfig(self): 
        """return a configuration object for the neural network
        
        The config object must contain the following parameters: 
        
        nnHiddenLayers : tuple
            A tuple of integers to configure the layers in the neural net
        batchnorm : bool
            A boolean to determine if batch normalization should be applied
        """
        raise NotImplementedError

    @abstractattr
    def get_model(self, config): 
        """return the siamese model (PyTorch model)

        Parameters 
        ----------
        config : dict
            A dictionary containing configuration variables relevant to the model.

        Returns
        -------
        A PyTorch model for the network.
        """

    ### OPTIONAL TO IMPLEMENT ###

    def get_trainer(self, hyperparams): 
        """Returns a PyTorch Lightning Trainer Object

        Parameters
        ----------
        hyperparams : dict
            A hyperparameter object with relevant values for trainer initialization.

        Returns
        -------
        A PyTorch Lightning Trainer Object
        """
        trainer = Trainer(min_epochs=hyperparams['min_epochs'],
                max_epochs=hyperparams['max_epochs'],
                min_steps=hyperparams['min_steps'],
                max_steps=hyperparams['max_steps'],
                gpus=1,
                devices=1,
                accelerator=hyperparams['device'],
                accumulate_grad_batches=hyperparams['accumulate_grad_batches'],
                # distributed_backend='dp',
                # weights_summary='full',
                # enable_benchmark=False,
                num_sanity_val_steps=0,
                # auto_find_lr=hparams.auto_find_lr,
                #   callbacks=[EarlyStopping(monitor='val_ci', mode="max", patience=5),
                #              checkpoint_callback],
                check_val_every_n_epoch=hyperparams['check_val_every_n_epoch'])
        
        return trainer

    def classify_target(self, y):
        max_val = max(y)
        min_val = min(y)
        vec_folds = list(range(1, 11))
        dif = (max_val - min_val)/10
        bins = [min_val-0.01]
        for elem in vec_folds:
            bins.append(min_val+dif*elem)
        result = pd.cut(y, bins, labels=vec_folds)
        return result

    def get_dataloaders(self, dataSet, cross_validation, random_pairs): 
        """Returns a tuple containing the training and then the testing PyTorch DataLoaders.

        Parameters
        ----------
        dataSet : pandas.DataFrame
            Takes in a Pandas DataFrame object.

        Returns
        -------
        A tuple with two objects. The first one is the training dataloader (PyTorch.DataLoader), the 
        second is the testing dataloader. 
        """
        y = dataSet['target']
        X = dataSet.iloc[:, 0:-1]
        loaders = []
        if cross_validation:
            num_folds = 5
            # gene_data = Dataset(dataSet, False, self.batch_size)
            # print(y)
            new_y = self.classify_target(y)
            # print(new_y)        
            skf = StratifiedKFold(n_splits=num_folds, random_state=None)
            result = skf.split(X,new_y)
            # train_idx, val_idx = train_test_split(list(range(gene_data.__len__())), test_size=0.2)
            count = 1
            for train_index, val_index in result:
                dS = Dataset(dataSet, True, self.batch_size, self.delta, train_index)
                num_pairs = len(dS._build_pairs(delta=self.delta))
                randoms = random.sample(dS._build_pairs(delta=0.0), num_pairs)
                train_dl = torch.utils.data.DataLoader(
                    dS,
                    batch_size=self.hyperparams['batch_size'], 
                    shuffle=True, 
                    num_workers=self.hyperparams['num_workers'],
                    multiprocessing_context='spawn',
                )
                # val_dl = Dataset(dataSet, True, self.batch_size, self.delta, val_index)
                val_dl = torch.utils.data.DataLoader(
                    Dataset(dataSet, True, self.batch_size, self.delta, val_index),
                    batch_size=self.hyperparams['batch_size'], 
                    shuffle=True, 
                    num_workers=self.hyperparams['num_workers'],
                    multiprocessing_context='spawn',
                )
                val_dataset = X.iloc[val_index]

                # train_aac = y.iloc[train_index]
                # val_aac = y.iloc[val_index]
                # tables = [(pd.DataFrame(y), "Whole"), (pd.DataFrame(train_aac), "Training"), (pd.DataFrame(val_aac), "Validation")]
                # aux = pd.concat([df.assign(dataset=k) for (df, k) in tables])
                # fig = sns.displot(aux, x="target", hue="dataset", kind="kde", fill=True, legend=True).set(title="AAC Distribution Comparison", xlabel="AAC Standarized", ylabel="Density")
                # fig.savefig('AAC Distribution Comparison-' + str(count) + '.png')
                loaders.append((train_dl, val_dl, val_dataset))
                count = count + 1
        else:
            gene_data = Dataset(dataSet, False, self.batch_size)
            train_idx, val_idx = train_test_split(list(range(gene_data.__len__())), test_size=0.2)
            train_dl = torch.utils.data.DataLoader(
                    Dataset(dataSet, True, self.batch_size, self.delta, train_idx),
                    batch_size=self.hyperparams['batch_size'], 
                    shuffle=True, 
                    num_workers=self.hyperparams['num_workers'],
                    multiprocessing_context='spawn',
                )
            if random_pairs:
                dS = Dataset(dataSet, True, self.batch_size, self.delta, train_idx)
                num_pairs = len(dS)
                randoms = random.sample(dS._build_pairs(delta=0.0), num_pairs)
                val_dl = torch.utils.data.DataLoader(
                        Dataset(dataSet, True, self.batch_size, 0.0, pre_built=True, pairs=randoms),
                        batch_size=self.hyperparams['batch_size'], 
                        shuffle=True, 
                        num_workers=self.hyperparams['num_workers'],
                        multiprocessing_context='spawn',
                    )
                val_dataset = dataSet.iloc[val_idx]
                loaders.append((train_dl, val_dl, val_dataset))
            else:
                """
                val_dl = torch.utils.data.DataLoader(
                        Dataset(dataSet, True, self.batch_size, self.delta, val_idx),
                        batch_size=self.hyperparams['batch_size'], 
                        shuffle=True, 
                        num_workers=self.hyperparams['num_workers'],
                        multiprocessing_context='spawn',
                    )
                """
                loaders.append((train_dl, None, None))
        return loaders


### INHERITING CLASSES ###


class deepCINET(BaseCINET): 
    def __init__(self, nnHiddenLayers=(128,512,128,0), **kwargs):
        # """
        # nnHiddenLayers : tuple of integers
        #     Describes the neural network architecture for deepCINET.
        # """
        self.nnHiddenLayers = nnHiddenLayers
        super().__init__(**kwargs)

    def _validate_params(self): 
        super()._validate_params()
        assert isinstance(self.nnHiddenLayers, tuple), 'nnHiddenLayers must be of type tuple'
        assert (len(self.nnHiddenLayers) == 4), 'nnHiddenLayers must have only four values'
        for i in range(len(self.nnHiddenLayers)):
            assert isinstance(self.nnHiddenLayers[i], int), 'values in nnHiddenLayers must be of type int'


    def getConfig(self): 
        return  {
            'nnHiddenLayers': self.nnHiddenLayers,
            'batchnorm': True,
        }
    
    def get_model(self, config):
        return DeepCINET(hyperparams=self.hyperparams, config=config, linear=False)
        

class ECINET(BaseCINET): 
    def getConfig(self): 
        return {
            'nnHiddenLayers': (0,0,0,0),
            'batchnorm': False,
            # TODO: Not hardcode these two following values
            'ratio': 0.4, 
            'reg_contr': 0.4,
        }

    def get_model(self, config):
        return DeepCINET(hyperparams=self.hyperparams, config=config, linear=True)


