# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import glob
import itertools
import logging
import os
from functools import reduce
from typing import Set

from sampletester import parser
from sampletester.parser import SCHEMA_TYPE_ABSENT as UNKNOWN_TYPE
from sampletester.sample_manifest import SCHEMA_TYPE_VALUE as MANIFEST_TYPE
from sampletester.testplan import SCHEMA_TYPE_VALUE as TESTPLAN_TYPE


def untyped_yaml_resolver(unknown_doc: parser.Document) -> str :
  """Determines how `parser.IndexedDocs` should classify `unknown_doc`

  This is a resolver for parser.IndexedDocs, used to resolve YAML docs that did
  not have a type field and thus could not be automatically classified. This
  resolver resolves using the filename, for backward compatibility: files ending
  in `.manifest.yaml` are categorized as manifest files, and remaining YAML
  files are categorized as testplan files.
  """
  ext_split = os.path.splitext(unknown_doc.path)
  ext = ext_split[-1]
  if ext == ".yaml":
    prev_ext = os.path.splitext(ext_split[0])[-1]
    if prev_ext == ".manifest":
      return MANIFEST_TYPE
    else:
      return TESTPLAN_TYPE
  return UNKNOWN_TYPE


def index_docs(file_patterns: Set[str]) -> parser.IndexedDocs:
  """Obtains manifests and testplans by indexing the specified paths or cwd.

  This function attempts to obtain all the manifests and testplans contained in
  the globs in `file_patterns`. If either no manifest or no testplan is obtained
  this way, it searches in all the paths under the cwd and registers the
  `file_patterns` matching the types not found in the previous step. In other
  words, if no manifests are found via the globs in `file_patterns`, it attempts
  to get manifests under the cwd, and similarly for testplans.
  """
  explicit_files = get_globbed(file_patterns)
  indexed_explicit = create_indexed_docs(*explicit_files)
  has_manifests = indexed_explicit.contains(MANIFEST_TYPE)
  has_testplans = indexed_explicit.contains(TESTPLAN_TYPE)
  if has_manifests and has_testplans:
    return indexed_explicit

  implicit_files = get_globbed(['**/*.yaml'])
  indexed_implicit = create_indexed_docs(*implicit_files)
  if not has_testplans:
    indexed_explicit.add_documents(*indexed_implicit.of_type(TESTPLAN_TYPE))
  if not has_manifests:
    indexed_explicit.add_documents(*indexed_implicit.of_type(MANIFEST_TYPE))
  return indexed_explicit

def create_indexed_docs(*all_paths: Set[str]) -> parser.IndexedDocs:
  """Returns a parser.IndexedDocs that contains all documents in `all_paths`.

  This is a helper for `indexed_docs()`, and is also used heavily in tests.
  """
  indexed_docs = parser.IndexedDocs(resolver=untyped_yaml_resolver)
  indexed_docs.from_files(*all_paths)
  return indexed_docs


def get_globbed(file_patterns: Set[str]) -> Set[str]:
  """Returns the set of files returned from globbing `file_patterns`"""
  return set(itertools.chain(*map(glob.glob, file_patterns)))
