from .handler import handle_train_transformer, handle_test_transformer, validate_transformer, handle_estimator
from sketch.util.dataframe import validate_column_names
from sketch.core.accuracy import binary_classification_accuracy
from sketch.util.datatype import convert_to_numpy
from joblib import Parallel, delayed
import numpy as np


class Pipeline:
	
	def __init__(self, steps):
		"""
		Args:
			steps (list): List of tuples containing transformers and estimators
			Each tuple contains (pkey, estimator/transformer, column_name, params)
		"""
		self._steps = steps
		self.model = dict()
		
		# Validate the transformers and estimators
		self._validate_steps()

	def _validate_steps(self):
		pkey, transformers, _, _ = zip(*self._steps[:-1])
		_, estimator, _ = self._steps[-1]
		
		# Validate transformer
		validate_transformer(transformers)
		
		# Validate estimator
		if not hasattr(estimator, "fit"):
			raise TypeError(
				f"Last step of Pipeline should implement fit "
				f"{estimator} {type(estimator)} doesnt")
		
		# Validate primary key
		if len(set(pkey)) != len(pkey):
			raise ValueError(
				f"Estimator names must be unique"
				f"{pkey}")
		
	def _fit(self, features, target, n_jobs, k_fold):
		pkey, estimators, columns, params = zip(*self._steps[:-1])
		
		# Check for columns in the DataFrame
		validate_column_names(features.columns, columns)
		
		# Transform features using parallelization
		transformed_features = Parallel(n_jobs=n_jobs, backend='multiprocessing')\
			(delayed(handle_train_transformer)(*i) for i in zip(
				[self]*len(estimators), [features.copy()]*len(estimators), pkey,
				estimators, columns, params))
		
		# Convert every feature to numpy array and concatenate
		transformed_features = convert_to_numpy(transformed_features)
		transformed_features = np.hstack(transformed_features)
		
		# Use estimator
		pkey, estimator, param = self._steps[-1]
		self._model = handle_estimator(
			self, estimator, pkey, transformed_features, target, params,
			binary_classification_accuracy, k_fold=k_fold)
		
	def _predict(self, features, n_jobs):
		pkey, estimators, columns, params = zip(*self._steps[:-1])
		
		# Check for columns in the DataFrame
		validate_column_names(features.columns, columns)
		
		# Transform features using parallelization
		transformed_features = Parallel(n_jobs=n_jobs, backend='multiprocessing')\
			(delayed(handle_test_transformer)(*i) for i in zip(
				[self] * len(estimators), [features.copy()] * len(estimators), pkey,
				estimators, columns, params))
		
		# Convert every feature to numpy array and concatenate
		transformed_features = convert_to_numpy(transformed_features)
		transformed_features = np.hstack(transformed_features)
		
		# Use estimator
		pkey, _, param = self._steps[-1]
		prediction = handle_estimator(
			self, None, pkey, transformed_features, None, params,
			binary_classification_accuracy, test=True)
		return prediction
		
	def fit(self, features, target, n_jobs=None, k_fold=None):
		"""
		Train the model using the transformations and estimator

		Args:
			features (pd.DataFrame): Independent variable of training data
			target (pd.Series): Dependent variable of training data
			n_jobs (int): Number of jobs to parallelize transformations
			k_fold (int): Number of fold validation

		Returns:
			Pipeline object
		"""
		self._fit(features, target, n_jobs, k_fold)
		return self
	
	def predict(self, features, n_jobs=None):
		"""
		Test the model using transformation and estimator
		
		Args:
			features (pd.DataFrame): Independent variable of test data
			n_jobs (int): Number of jobs to parallelize transformations
			
		Returns:
			predictions
		"""
		predictions = self._predict(features, n_jobs)
		return predictions
