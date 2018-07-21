import os
from glob import glob
from concurrent.futures import ProcessPoolExecutor
import functools
import pystache
from .shared import get_yaml_dict, rel_to_cwd
from .xterm import approx_xterm_colors


class TemplateGroup(object):
    """Representation of a template group, i.e. a group of templates specified
    in a config.yaml."""

    def __init__(self, base_path):
        self.base_path = base_path
        self.name = os.path.basename(base_path.rstrip('/'))
        self.templates = self.get_templates()

    def get_templates(self):
        """
        Return a list of template_dicts based on the config.yaml in
        $self.base_path. Keys correspond to templates and values represent
        further settings regarding each template. A pystache object containing
        the parsed corresponding mustache file is added to the sub-dictionary.
        """
        config_path = rel_to_cwd(self.base_path, 'templates', 'config.yaml')
        templates = get_yaml_dict(config_path)
        for temp, sub in templates.items():
            mustache_path = os.path.join(get_parent_dir(config_path),
                                         '{}.mustache'.format(temp))
            sub['parsed'] = get_pystache_parsed(mustache_path)
        return templates


def transform_template(scheme, template):
    """Apply $scheme to $template and return the result string."""
    result = pystache.render(template, scheme)
    return result


def get_parent_dir(base_dir, level=1):
    "Get the directory $level levels above $base_dir."
    while level > 0:
        base_dir = os.path.dirname(base_dir)
        level -= 1
    return base_dir


def get_pystache_parsed(mustache_file):
    """Return a ParsedTemplate instance based on the contents of
    $mustache_file."""
    with open(mustache_file, 'r') as file_:
        parsed = pystache.parse(file_.read())
    return parsed


def get_template_dirs():
    """Return a set of all template directories."""
    temp_glob = rel_to_cwd('templates', '**', 'templates', 'config.yaml')
    temp_groups = glob(temp_glob)
    temp_groups = [get_parent_dir(path, 2) for path in temp_groups]
    return set(temp_groups)


def get_scheme_dirs():
    """Return a set of all scheme directories."""
    scheme_glob = rel_to_cwd('schemes', '**', '*.yaml')
    scheme_groups = glob(scheme_glob)
    scheme_groups = [get_parent_dir(path) for path in scheme_groups]
    return set(scheme_groups)


def get_scheme_files(patterns=None):
    """Return a list of all (or those matching $pattern) yaml (scheme)
    files."""
    patterns = patterns or ['*']
    pattern_list = ['{}.yaml'.format(pattern) for pattern in patterns]
    scheme_files = []
    for scheme_path in get_scheme_dirs():
        for pattern in pattern_list:
            file_paths = glob(os.path.join(scheme_path, pattern))
            scheme_files.extend(file_paths)

    return scheme_files


def format_scheme(scheme, slug):
    """Change $scheme so it can be applied to a template."""
    scheme['scheme-name'] = scheme.pop('scheme')
    scheme['scheme-author'] = scheme.pop('author')
    scheme['scheme-slug'] = slug
    bases = ['base{:02X}'.format(x) for x in range(0, 16)]
    for base in bases:
        scheme['{}-hex'.format(base)] = scheme.pop(base)
        scheme['{}-hex-r'.format(base)] = scheme['{}-hex'.format(base)][0:2]
        scheme['{}-hex-g'.format(base)] = scheme['{}-hex'.format(base)][2:4]
        scheme['{}-hex-b'.format(base)] = scheme['{}-hex'.format(base)][4:6]

        scheme['{}-rgb-r'.format(base)] = str(
            int(scheme['{}-hex-r'.format(base)], 16))
        scheme['{}-rgb-g'.format(base)] = str(
            int(scheme['{}-hex-g'.format(base)], 16))
        scheme['{}-rgb-b'.format(base)] = str(
            int(scheme['{}-hex-b'.format(base)], 16))

        scheme['{}-dec-r'.format(base)] = str(
            int(scheme['{}-rgb-r'.format(base)]) / 255)
        scheme['{}-dec-g'.format(base)] = str(
            int(scheme['{}-rgb-g'.format(base)]) / 255)
        scheme['{}-dec-b'.format(base)] = str(
            int(scheme['{}-rgb-b'.format(base)]) / 255)

    hex_colors = [scheme['base{:02X}-hex'.format(base)]
        for base in range(0, 16)]

    for base, xterm_color in enumerate(approx_xterm_colors(hex_colors)):
        scheme['base{:02X}-xterm'.format(base)] = str(xterm_color)


def slugify(scheme_file):
    """Format $scheme_file_name to be used as a slug variable."""
    scheme_file_name = os.path.basename(scheme_file)
    if scheme_file_name.endswith('.yaml'):
        scheme_file_name = scheme_file_name[:-5]
    return scheme_file_name.lower().replace(' ', '-')


def build_single(templates, base_output_dir, scheme_file):
    """Build colorscheme for a single $scheme_file using all TemplateGroup
    instances in $templates."""
    scheme = get_yaml_dict(scheme_file)
    scheme_slug = slugify(scheme_file)
    format_scheme(scheme, scheme_slug)

    scheme_name = scheme['scheme-name']
    print('Building colorschemes for scheme "{}"…'.format(scheme_name))
    for temp_group in templates:

        for _, sub in temp_group.templates.items():
            output_dir = os.path.join(base_output_dir,
                                      temp_group.name,
                                      sub['output'])
            try:
                os.makedirs(output_dir)
            except FileExistsError:
                pass

            if sub['extension'] is not None:
                filename = 'base16-{}{}'.format(scheme_slug, sub['extension'])
            else:
                filename = 'base16-{}'.format(scheme_slug)

            build_path = os.path.join(output_dir, filename)
            with open(build_path, 'w') as file_:
                file_content = pystache.render(sub['parsed'], scheme)
                file_.write(file_content)

    print('Built colorschemes for scheme "{}".'.format(scheme_name))

def build_from_job_list(scheme_files, templates, base_output_dir):
    """Use $scheme_files as a job lists and build base16 templates using
    $templates (a list of TemplateGroup objects)."""

    entry_func = functools.partial(build_single, templates, base_output_dir)
    with ProcessPoolExecutor() as executor:
        executor.map(entry_func, scheme_files)

def build(templates=None, schemes=None, base_output_dir=None):
    """Main build function to initiate building process."""
    template_dirs = templates or get_template_dirs()
    scheme_files = get_scheme_files(schemes)
    base_output_dir = base_output_dir or rel_to_cwd('output')

    # raise LookupError if there is not at least one template or scheme
    # to work with
    if not template_dirs or not scheme_files:
        raise LookupError

    # raise PermissionError if user has no write acces for $base_output_dir
    try:
        os.makedirs(base_output_dir)
    except FileExistsError:
        pass

    if not os.access(base_output_dir, os.W_OK):
        raise PermissionError

    templates = [TemplateGroup(path) for path in template_dirs]

    build_from_job_list(scheme_files, templates, base_output_dir)
    print('Finished building process.')
