from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='wallabag-client',
    use_scm_version=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    package_data={'wallabag': ['*.css']},
    include_package_data=True,
    url='https://github.com/artur-shaik/wallabag-client',
    author='Artur Shaik',
    author_email='artur@shaik.link',
    description=('A command-line client for the self-hosted '
                 '`read-it-later` app Wallabag'),
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',

    install_requires=[
        'beautifulsoup4',
        'pycryptodome',
        'requests',
        'click',
        'yaspin',
        'click_repl',
        'pyxdg',
        'colorama',
        'delorean',
        'humanize',
        'lxml',
        'tzlocal',
        'tabulate',
        'packaging',
        'markdownify',
        'textual',
    ],
    tests_require=[
        'pytest',
    ],

    entry_points='''
        [console_scripts]
        wallabag=wallabag.wallabag:cli
        wallabag-tui=wallabag.tui:main
    '''
)
