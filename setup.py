

from setuptools import setup, find_packages


setup(name="tap-zoho-crm",
      version="0.1.0",
      description="Singer.io tap for extracting data from Zoho-CRM API",
      author="Stitch",
      url="http://singer.io",
      classifiers=["Programming Language :: Python :: 3 :: Only"],
      py_modules=["tap_zoho_crm"],
      install_requires=[
        "singer-python==6.8.0",
        "requests==2.34.2",
        "backoff==2.2.1",
        "parameterized==0.9.0"
      ],
      extras_require={"dev": ["pylint", "ipdb", "pytest"]},
      entry_points="""
          [console_scripts]
          tap-zoho-crm=tap_zoho_crm:main
      """,
      packages=find_packages(),
      package_data = {
          "tap_zoho_crm": ["schemas/*.json"],
      },
      include_package_data=True,
)
