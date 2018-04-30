from setuptools import setup, find_packages


setup(
    name='budgettracker',
    version='1.6.0',
    url='http://github.com/maximebf/budgettracker',
    license='MIT',
    author='Maxime Bouroumeau-Fuseau',
    author_email='maxime.bouroumeau@gmail.com',
    description='Simple budget tracking app',
    packages=find_packages(),
    package_data={
        'budgettracker': ['web/templates/*', 'web/static/*'],
    },
    zip_safe=False,
    platforms='any',
    install_requires=[
        'requests',
        'beautifulsoup4',
        'unicodecsv',
        'flask',
        'monthdelta',
        'ofxparse',
        'PyYAML'
    ],
    entry_points='''
        [console_scripts]
        budgettracker=budgettracker.cli:main
    '''
)
