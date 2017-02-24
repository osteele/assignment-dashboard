# noqa: D100
import os
import re

from setuptools import setup

GIT_DEPENDENCY_RE = r'^(?:git\+)(.+)\.git@(.+?)(#egg=(.+)-(.+))'
requirements_txt = open(os.path.join(os.path.dirname(__file__), 'requirements.txt')).read()
requirements = re.findall(r'^(?:-e\s+)?([^\s#][^\s]+)', requirements_txt, re.M)
install_requires = [re.sub(GIT_DEPENDENCY_RE, r'\4==\5', r) for r in requirements]
dependency_links = [re.sub(GIT_DEPENDENCY_RE, r'\1/archive/\2.tar.gz\3', r) for r in requirements if re.match(GIT_DEPENDENCY_RE, r)]

setup(name='assignment_dashboard',
      packages=['assignment_dashboard'],
      include_package_data=True,
      version='0.1',
      description="A web app that inspects forks of an GitHub assignment repo",
      long_description="Display the a GitHub repo's forks, by file, and collate Jupyter notebooks",
      classifiers=[
          'Intended Audience :: Developers',
          'Intended Audience :: Education',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3'
          'Programming Language :: Python :: 3.5'
      ],
      url='http://github.com/osteele/assignment-dashboard',
      author='Oliver Steele',
      author_email='steele@osteele.com',
      license='MIT',
      dependency_links=dependency_links,
      install_requires=install_requires
      )
