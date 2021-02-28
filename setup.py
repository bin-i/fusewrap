from setuptools import setup

setup(
    name='fusewrap',
    version='0.0.1',
    py_modules=['fusewrap'],
    install_requires=[
        'argparse',
        'argcomplete'
    ],
    entry_points='''
        [console_scripts]
        fusewrap=fusewrap:main
    ''',
)