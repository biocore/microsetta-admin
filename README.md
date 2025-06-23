# microsetta-admin
An admin interface to support The Microsetta Initiative

## Installation
Other projects should be installed first.<br>
https://github.com/biocore/microsetta-interface.git <br>
https://github.com/charles-cowart/microsetta-private-api.git

Create a new `conda` environment containing `flask` and other necessary packages:
```
conda create --name test-microsetta-admin python=3.7
```

Once the conda environment is created, activate it:
```
conda activate test-microsetta-admin
```

Ensure that the `conda-forge` channel has been added to the conda install and run:
```
conda install --yes --file ci/conda_requirements.txt
```

Install additional requirements using pip:
```
pip install -r ci/pip_requirements.txt
```

Install vi 'make' command and 'Makefile'.
```
make install
```

Lastly, add nodejs.
```
conda install -c conda-forge nodejs
```

To run unittests:
```
make test
```
