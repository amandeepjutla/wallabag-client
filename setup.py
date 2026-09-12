# Packaging maintenance: Kera (GPT-6 Astra)
# Created: 2026-09-12
from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='wallabag-client',
    use_scm_version={"fallback_version": "0.1.dev0"},
    packages=find_packages('src'),
    package_dir={'': 'src'},
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
        'beautifulsoup4>=4.9.1',
        'pycryptodome>=3.9.8',
        'requests>=2.11.1',
        'click>=8.0',
        'yaspin',
        'click_repl>=0.2.0',
        'pyxdg',
        'colorama>=0.4.3',
        'delorean',
        'humanize',
        'lxml',
        'tzlocal',
        'tabulate',
        'packaging',
        'markdownify',
        'textual>=0.44.0',
    ],
    entry_points='''
        [console_scripts]
        wallabag=wallabag.wallabag:cli
        wallabag-tui=wallabag.tui:main
    '''
)
