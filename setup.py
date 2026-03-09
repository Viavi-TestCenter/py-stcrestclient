import os, sys
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def main():
    setup(
        name='stcrestclient',
        version= '1.9.5',
        author='Spirent',
        author_email='support@spirent.com',
        url='https://github.com/Spirent-STC/py-stcrestclient',
        description='stcrestclient: Client modules for STC ReST API',
        long_description = 'See https://github.com/Spirent-STC/py-stcrestclient#python-stc-rest-api-client-stcrestclient',
        license='http://www.opensource.org/licenses/mit-license.php',
        keywords='Spirent TestCenter API',
        classifiers=['Development Status :: 5 - Production/Stable',
                     'Intended Audience :: Developers',
                     'License :: OSI Approved :: MIT License',
                     'Operating System :: POSIX',
                     'Operating System :: Microsoft :: Windows',
                     'Operating System :: MacOS :: MacOS X',
                     'Topic :: Software Development :: Libraries',
                     'Topic :: Utilities',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 2.7',
                     'Programming Language :: Python :: 3'],
        packages=['stcrestclient'],
        entry_points={
            'console_scripts': [
                'tccsh = stcrestclient.tccsh:main',
                'stcinfo = stcrestclient.systeminfo:main'],
        },
        install_requires=['requests>=2.7'],
        zip_safe=True,
        )


if __name__ == '__main__':
    main()
