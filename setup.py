from setuptools import setup, find_packages

setup(
    name='tomoshell',
    version='0.1',
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='https://github.com/ufo-kit',
    packages=find_packages(),
    package_data={'':['tomoshell.ui']},
    scripts=['bin/tomoshell'],
    description='Basic tomographic reconstruction GUI',
    install_requires=['pyqtgraph'],
    zip_safe=False,
)

