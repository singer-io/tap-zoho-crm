

from setuptools import setup, find_packages


setup(name="tap-zoho-crm",
      version="0.0.1",
      description="Singer.io tap for extracting data from Zoho-CRM API",
      author="Stitch",
      url="http://singer.io",
      classifiers=["Programming Language :: Python :: 3 :: Only"],
      py_modules=["tap_zoho_crm"],
      install_requires=[
        "singer-python==6.1.1",
        "requests==2.32.4",
        "backoff==2.2.1",
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
