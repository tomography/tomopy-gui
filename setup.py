from setuptools import setup, find_packages

setup(
    name='tomoshell',
    version=open('VERSION').read().strip(),
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='https://github.com/ufo-kit',
    packages=find_packages(),
    package_data={'':['tomopy.ui']},
    scripts=['bin/tomopyui'],
    description='Basic tomographic reconstruction GUI',
    install_requires=['pyqtgraph'],
    zip_safe=False,
)

