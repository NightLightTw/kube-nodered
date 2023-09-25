from typing import NamedTuple

import kfp
from kfp import dsl
from kfp.components import func_to_container_op, InputPath, OutputPath
import kfp.components as components
import datetime
import os

def load_data_func(log_folder:str) -> NamedTuple('Outputs', [('x_train', str), ('y_train', str), ('x_test', str), ('y_test', str)]):
    from typing import NamedTuple
    import os
    import tensorflow as tf
    import numpy as np
    
    # START_DATASET_CODE
    dataset = tf.keras.datasets.mnist
    # END_DATASET_CODE

    (x_train, y_train), (x_test, y_test) = dataset.load_data()
    x_train, x_test = x_train / 255.0, x_test / 255.0
    
    np.save(os.path.join(log_folder, 'x_train.npy'), x_train)
    np.save(os.path.join(log_folder, 'y_train.npy'), y_train)
    np.save(os.path.join(log_folder, 'x_test.npy'), x_test)
    np.save(os.path.join(log_folder, 'y_test.npy'), y_test)
    result = NamedTuple('Outputs', [('x_train', str), ('y_train', str), ('x_test', str), ('y_test', str)])
    return result(
        os.path.join(log_folder, 'x_train.npy'),
        os.path.join(log_folder, 'y_train.npy'),
        os.path.join(log_folder, 'x_test.npy'),
        os.path.join(log_folder, 'y_test.npy')
    )

def model_func(epochs:int, model_name:str, log_folder:str, x_train_path: str, y_train_path: str, x_test_path: str, y_test_path: str) -> NamedTuple('Outputs', [('logdir', str), ('accuracy', float)]):
    import tensorflow as tf
    import numpy as np
    import datetime
    import json
    import os
    from sklearn.metrics import accuracy_score
    
    import joblib
    print('model_func:', log_folder)
    
    x_train = np.load(x_train_path)
    y_train = np.load(y_train_path)
    x_test = np.load(x_test_path)
    y_test = np.load(y_test_path)
    
    x_train = x_train.reshape(x_train.shape[0], -1)
    x_test = x_test.reshape(x_test.shape[0], -1)

    def create_model():
        # START_MODEL_CODE
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(n_estimators=100, criterion = 'gini')
        # END_MODEL_CODE
        
    model = create_model()
    
    # START_TRAIN_CODE

    # END_TRAIN_CODE
    
    ### add log
    log_dir = os.path.join(log_folder, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    ######
    
    # Train the model
    model.fit(x_train, y_train)
    
    # Get predictions
    y_pred = model.predict(x_test)
    
    # Get accuracy
    accuracy = accuracy_score(y_test, y_pred)
    
    model_path = os.path.join(log_folder, model_name, 'model.joblib') # remove 1
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    
    print('logdir:', log_dir)
    print('accuracy', accuracy)
    accuracy = float(accuracy)
    return ([log_dir, accuracy])

@dsl.pipeline(
   name='Final pipeline',
   description='A pipeline to train a model on dataset output accuracy.'
)

def final_pipeline(epochs=5, model_name="model00",):

    log_folder = '/data'
    pvc_name = "mypvc"
    # START_DEPLOY_CODE
    model_name = "model08"
    # END_DEPLOY_CODE
    vop = dsl.VolumeOp(
        name=pvc_name,
        resource_name="newpvc",
        size="1Gi",
        modes=dsl.VOLUME_MODE_RWO
    )
    
    load_data_op = func_to_container_op(
        func=load_data_func,
        base_image="tensorflow/tensorflow:2.0.0-py3"
    )
    model_op = func_to_container_op(
        func=model_func,
        base_image="tensorflow/tensorflow:2.0.0-py3",
        packages_to_install=["scikit-learn"]
    )
    ########################################################
    load_data_task = load_data_op(log_folder).add_pvolumes({
        log_folder:vop.volume,
    }).set_cpu_limit("1").set_cpu_request("0.5")
    
    model_task = model_op(
        epochs,
        model_name,
        log_folder,
        load_data_task.outputs['x_train'],
        load_data_task.outputs['y_train'],
        load_data_task.outputs['x_test'],
        load_data_task.outputs['y_test'],
    ).add_pvolumes({
        log_folder:vop.volume,
    }).set_cpu_limit("1").set_cpu_request("0.5")

kfp.compiler.Compiler().compile(final_pipeline, 'final_pipeline.yaml')
print("Compile SUCCESS!")