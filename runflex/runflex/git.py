#!/usr/bin/env python

import runflex
import git

# # Fix for the "ValueError: SHA could not be resolved, git returned: b''" error
# # https://github.com/gitpython-developers/GitPython/issues/1016
# # Seems to be a git bug, maybe ubuntu-specific ...
# #
# class Repo(git.Repo):
#     def __init__(self, *args, **kwargs):
#         self.repo = git.Repo(*args, **kwargs)
#         self._safe_directory_bkp = None
#
#     def __enter__(self):
#         with self.repo.config_writer(config_level='global') as config:
#             self._safe_directory_bkp = config.get_value('safe', 'directory', None)
#             config.set_value('safe', 'directory', str(runflex.prefix))
#         return self.repo
#
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         with self.repo.config_writer(config_level='global') as config:
#             if self._safe_directory_bkp is not None:
#                 config.set_value('safe', 'directory', str(runflex.prefix))
#             else :
#                 config.remove_option('safe', 'directory')
#
#
# with Repo(runflex.prefix) as repo:
#     commit = repo.head.object
#
#
# #repo = git.Repo(runflex.prefix)
# #with repo.config_writer(config_level='global') as config :
# #    config.set_value('safe', 'directory', str(runflex.prefix))
#
# #commit = repo.head.object

commit = git.Repo(runflex.prefix).head.object