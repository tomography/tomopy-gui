from setuptools import setup, find_packages

setup(
    name='ufot',
    version=open('VERSION').read().strip(),
    #version=__version__,
    author='Matthias Vogelgesang',
    author_email='matthias.vogelgesang@kit.edu',
    url='https://github.com/ufo-kit',
    packages=find_packages(),
    package_data={'':['gui.ui', 'roi.ui']},
    scripts=['bin/ufot'],
    description='tofu for tomopy',
    install_requires=['pyqtgraph'],
    zip_safe=False,
)

