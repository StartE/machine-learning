"""
Example usage

Convert existing jupyter notebook to an airbnb knowledge repo format
- python converter.py --ml_repo . --knowledge_repo knowledge-repo

Deploying the webapp
- knowledge_repo --repo knowledge-repo deploy
"""
import os
import re
import json
import subprocess
from dateutil import parser as date_parser


def main(ml_repo, knowledge_repo, inplace):
    ml_repo_path = os.path.abspath(ml_repo)
    knowledge_repo_path = os.path.abspath(knowledge_repo)
    if not os.path.isdir(knowledge_repo_path):
        init_knowledge_repo(knowledge_repo_path)

    convert_all_posts(ml_repo_path, knowledge_repo_path, inplace)


def init_knowledge_repo(path):
    cmd = 'knowledge_repo --repo {} init'.format(path)
    subprocess.call(cmd, shell=True)


def convert_all_posts(path, knowledge_repo_path, inplace):
    """Recursive walk down all directory to perform the conversion"""
    if os.path.isdir(path):
        files = [os.path.join(path, f) for f in os.listdir(path)]
        for f in files:
            convert_all_posts(f, knowledge_repo_path, inplace)

    elif '-converted' not in path:
        head, ext = os.path.splitext(path)
        if ext == ".ipynb":
            try:
                converter = IpynbConverter(knowledge_repo_path, inplace)
                notebook = converter.convert(path)
                converter.add(notebook)
            except Exception as e:
                print('Skipping: {}'.format(path))
                print(e)


class IpynbConverter:
    """
    Converts Jupyter notebook to airbnb knowledge repo format [1]_.

    Parameters
    ----------
    knowledge_repo_path : str
        Path to store the airbnb knowledge repo-ed notebook.

    inplace : bool
        Whether to perform the conversion inplace or not. If
        false, then it will create a new notebook that has the
        '-converted' appended to the file name.

    Attributes
    ----------
    date_created_ : str
        Input notebook's creation date.

    date_updated_ : str
        Input notebook's latest updated date.

    tags_ : str
        The notebook's filename is use as the tag in this automated
        conversion process. e.g. /Users/ethen/machine-learning/trees/decision_tree.ipynb,
        we would use 'decision_tree' as the tag.

    github_link_ : str
        Notebook's original link on github.

    title_ : str
        Notebook's title, uses the first level 1 markdown header that's not
        'Table of Contents' that could be automatically generated by newer
        version of notebook. e.g. # Decision Tree (Classification)\n, then
        Decision Tree (Classification) would be our title.

    References
    ----------
    .. [1] `Airbnb knowledge repo
            <https://github.com/airbnb/knowledge-repo>`_
    """

    AUTHOR = 'Ethen Liu'
    DATE_FORMAT = '%Y-%m-%d'
    REPO_NAME = 'machine-learning'
    BASE_URL = 'https://github.com/ethen8181/'

    def __init__(self, knowledge_repo_path, inplace):
        self.inplace = inplace
        self.knowledge_repo_path = knowledge_repo_path

    def convert(self, path):
        """
        Convert the input path's notebook to a knowledge repo. This
        will add a mandatory raw cell that contains the yaml information
        needed by the knowledge repo and an additional cell that contains
        link to the notebook on github.

        Parameters
        ----------
        path : str
            Path that has the '.ipynb' extension.

        Returns
        -------
        notebook : dict
            Updated Jupyter notebook's raw json represented in dictionary format.
            Ready to be passed to the .add method to add to the knowledge repo.
        """
        self.date_created_ = self._date_created(path)
        self.date_updated_ = self._date_updated(path)
        self.tags_, self.github_link_ = self._tags_and_github_link(path)
        with open(path, encoding='utf-8') as f:
            notebook = json.load(f)

        self.title_ = self._title(notebook)

        # prepend the dictionary header to notebook['cells']
        notebook['cells'] = ([self._construct_header()] +
                             [self._construct_github_link_cell()] +
                             notebook['cells'])
        if not self.inplace:
            head, ext = os.path.splitext(path)
            head += '-converted'
            path = head + ext

        self._path = path
        return notebook

    def _date_created(self, path):
        """Grab the date of creation through git log."""
        cmd = 'git log --diff-filter=A --follow --format=%cd -1 -- {}'.format(path)
        return self._git_date_cmd(cmd)

    def _date_updated(self, path):
        """Grab the last date modified through git log."""
        cmd = 'git log --format=%cd -1 -- {}'.format(path)
        return self._git_date_cmd(cmd)

    def _git_date_cmd(self, cmd):
        """Run bash command to retrieve and format date string."""
        date_str = subprocess.check_output(cmd, shell=True)
        date_dt = date_parser.parse(date_str)
        formatted_date = date_dt.strftime(self.DATE_FORMAT)
        return formatted_date

    def _tags_and_github_link(self, path):
        """
        Use file name as tags, e.g. /Users/ethen/machine-learning/trees/decision_tree.ipynb
        we would use 'decision_tree' as the tag
        """
        _, file_path = path.split(self.REPO_NAME)
        _, file_name = os.path.split(file_path)
        tags, _ = os.path.splitext(file_name)

        # /blob/master indicates github master branch
        link = self.BASE_URL + self.REPO_NAME + '/blob/master' + file_path
        return tags, link

    def _title(self, notebook):
        """
        A title in the notebook always starts with the '#' indicating a
        markdown level 1 header e.g. # Decision Tree (Classification)\n
        thus we can just parse all the text in between the '#' and the line break '\n'
        """

        # TODO : we could fall back to the file path if it doesn't exist perhaps?
        title_pattern = re.compile('# (.*)\n')
        for cell in notebook['cells']:
            if cell['cell_type'] == 'markdown':
                # the [0] indicates the # title pattern
                # should always appear in the first line
                source = cell['source'][0]
                matched = title_pattern.match(source)
                if matched is not None:
                    title = matched.group(1)
                    # newer version of notebooks includes a
                    # Table of Contents automatically in the first
                    # cell, skip that and find the next level 1 header
                    if not title == 'Table of Contents':
                        break
        return title

    def _construct_header(self):
        """Create a knowledge repo style header as a dictionary."""

        def flatten_list(l):
            """
            Although not needed for the current version, we could
            have multiple tags and authors, in that case we would
            need to flatten them out.
            """
            flat = []
            for item in l:
                if isinstance(item, list):
                    flat += item
                else:
                    flat.append(item)

            return flat

        header = {'cell_type': 'raw', 'metadata': {}}

        # header text required by the knowledge repo
        # a '- ' in front is required for knowledge repo tag
        header_text = [
            '---',
            'title: {}'.format(self.title_),
            'authors:',
            '- {}'.format(self.AUTHOR),
            'tags:',
            '- ' + self.tags_,
            'created_at: {}'.format(self.date_created_),
            'updated_at: {}'.format(self.date_updated_),
            'tldr: Nothing for tldr section as of now.',
            '---']

        header_text = flatten_list(header_text)
        header_text = [text + '\n' for text in header_text[:-1]] + [header_text[-1]]
        header['source'] = header_text
        return header

    def _construct_github_link_cell(self):
        """Add a cell that contains link to original notebook on github"""
        github_link_cell = {
            'cell_type': 'markdown',
            'metadata': {},
            'source': ['Link to original notebook: {}'.format(self.github_link_)]}
        return github_link_cell

    def add(self, notebook):
        """
        Add the converted notebook to the knowledge repo.

        Parameters
        ----------
        notebook : dict
            Jupyter notebook's raw json represented in dictionary format.
        """
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(notebook, f)

        # create a run knowledge repo command
        destination = os.path.join(self.knowledge_repo_path, 'project', self.tags_)
        cmd = 'knowledge_repo --repo {} add {} -p {}'.format(
            self.knowledge_repo_path, self._path, destination)

        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE,
            stderr=subprocess.STDOUT, shell=True)
        p.communicate(input=b'generated by automated airbnb knowledge repo setup')

        if not self.inplace:
            os.remove(self._path)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Convert the machine-learning repository to an Airbnb Knowledge Repo.')
    parser.add_argument(
        '--ml_repo', type=str, help='Path to the root directory of the machine-learning repo.')
    parser.add_argument(
        '--knowledge_repo', type=str, help='Path to the knowledge repo.')
    parser.add_argument(
        '--inplace', action='store_true', help='Modify the existing .ipynb in place.')
    args = vars(parser.parse_args())
    main(**args)