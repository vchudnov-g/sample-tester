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

import collections
import logging
import os
import yaml

from typing import Callable
from typing import Dict
from typing import List
from typing import Set
from typing import Tuple

SCHEMA_TYPE_KEY = 'type'
SCHEMA_TYPE_ABSENT = '(no type)' # for indexing docs with no SCHEMA_TYPE_KEY
SCHEMA_TYPE_SEPARATOR = '/'

Document = collections.namedtuple('Document', ['path', 'obj'])

def full_schema_value(type_value: str, subtype_value: str) -> str:
  """Returns a full schema value string from the type and subtype parts."""
  return f'{type_value}{SCHEMA_TYPE_SEPARATOR}{subtype_value}'

class IndexedDocs(object):
  def __init__(self,
               strict: bool = False,
               resolver: Callable[[Document], str] = None):
    """Initialized IndexedDocs

    Args:
      strict: If true, raise an Exception if a top-level 'type' field is absent
      resolver: a function that will be used if `strict` is not set to
        categorize documents that do not have a top-level 'type' field. The
        function is passed an uncategorized doc and should return a type string
        that will be used to categorize the document.
    """
    self.keyed_docs = {}
    self.strict = strict
    self.resolver = resolver

  def contains(self, *type_names: str) -> bool:
    """Returns True iff 1+ docs exist for each schema type in`type_names`"""
    return all([name in self.keyed_docs for name in type_names])

  def from_files(self, *paths: str):
    """Adds all the documents found in `paths`."""
    for file_name in only_files_in(paths):
      file_path = os.path.abspath(file_name)
      with open(file_path, 'r') as stream:
        content = stream.read()
        self.add(content, file_path)

  def from_strings(self, *sources: Tuple[str, str]):
    """Adds all the documents found in `sources`.

    Args:
      sources: a pair of YAML text and a description
    """
    for description, content in sources:
      self.add(content, description)

  def add(self, content:str, file_name: str):
    """Adds each YAML document in content as a Document indexed by its 'type'.

    This function parses `content` and extracts all YAML documents it finds
    there.  The documents are stored in lists of `Document` objects grouped and
    indexed by the value of their top-level 'type' field.  If `strict` was set,
    untyped documents raise an exception. Otherwise, if a resolver was provided,
    it is called for each untyped document and the document is reclassified
    according the type value returned by the provider. If no resolved was
    provided, the untyped documents are put into their own list with type given
    by `SCHEMA_TYPE_ABSENT`.
    """
    self.add_documents(*[Document(file_name, doc) for doc in yaml.load_all(content)])

  def add_documents(self, *documents: Document):
    """Adds each doc in `documents` under the right schema type key."""
    for doc in documents:
      specified_type = (doc.obj.get(SCHEMA_TYPE_KEY, None)
                        if isinstance(doc.obj,  dict)
                        else None)

      if not specified_type:
        msg = f'no top-level "{SCHEMA_TYPE_KEY}" field specified'
        if self.strict:
          raise SyntaxError(msg)
        logging.warning(msg)

      if not isinstance(specified_type, str):
        msg = (f'top level "{SCHEMA_TYPE_KEY}" field is not '
               f'a string: {specified_type}')
        if self.strict:
          raise SyntaxError(msg)
        logging.warning(msg)
        specified_type = SCHEMA_TYPE_ABSENT

      type_name = specified_type.split(SCHEMA_TYPE_SEPARATOR, 1)[0]
      self._add_one(type_name, doc)
    self.resolve_uncategorized()


  def _add_one(self, type_name: str, doc: Document):
    """Adds `doc` to the list of documents with the given type."""
    similar_docs = self.keyed_docs.get(type_name, [])
    if not similar_docs:
      self.keyed_docs[type_name] = similar_docs
    similar_docs.append(doc)

  def of_type(self, type_name: str) -> List[Document]:
    """Returns a list of all `Document`s with the given type."""
    return self.keyed_docs.get(type_name, [])

  def resolve_uncategorized(self):
    """Categorizes all documents of unknown type by calling the resolver."""
    if not self.resolver:
      return

    unknowns = self.of_type(SCHEMA_TYPE_ABSENT)
    for idx, unknown_doc in enumerate(unknowns):
      new_type = self.resolver(unknown_doc)
      if not new_type or new_type == SCHEMA_TYPE_ABSENT:
        continue

      # mark the doc as now being of the new type, and no longer of unknown type
      self._add_one(new_type, unknown_doc)
      unknowns[idx]=None

    # remove `None`s from the list of unknown docs
    self.keyed_docs[SCHEMA_TYPE_ABSENT] = [doc for doc in unknowns if doc]


def only_files_in(paths: Set[str]) -> Set[str]:
  """Returns only those elements of `paths` that are files"""
  return {fname for fname in paths if os.path.isfile(fname)}


class SyntaxError(Exception):
  pass
