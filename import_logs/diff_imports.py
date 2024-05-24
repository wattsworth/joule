import_stmts = []
with open("base_imports.txt") as f:
    f.readline() # ignore the first line
    for line in f:
        fields =  line.split('|')
        import_stmts.append(fields[-1])

# create python click command to read in a file 
# and compare each line to the import_stmts list
# if the line ends with an item in this list then
# ignore it, otherwise write it out to a file that
# ends with _diff.txt
import click
@click.command()
@click.argument('file', type=click.File('r'))
def diff_imports(file):
    with open(file.name.replace('.txt', f'_diff.txt'), 'w') as f:
        for line in file:
            if not any(line.endswith(stmt) for stmt in import_stmts):
                f.write(line)

if __name__ == '__main__':
    diff_imports()