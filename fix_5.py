import struct
import svgwrite

# Define the structs from codec.py
class MFCFileHeader(struct.Struct):
    def __init__(self):
        super().__init__('<'
                         '4s'  # magic
                         'I'   # version
                         'I'   # num_blocks
                         'I'   # block_size
                         'I'   # reserved
                         )

class MFCBlockRecord(struct.Struct):
    def __init__(self):
        super().__init__('<'
                         'I'   # block_id
                         'I'   # block_size
                         'I'   # data_offset
                         'I'   # data_size
                         )

# Create the SVG diagram
def create_diagram():
    dwg = svgwrite.Drawing('docs/diagrams/mfc_layout.svg', (800, 200))

    # Draw the file header
    dwg.add(dwg.rect(insert=(10, 10), size=(100, 20), fill='lightblue'))
    dwg.add(dwg.text('MFC File Header', insert=(15, 20), font_size=12))

    # Draw the block records
    dwg.add(dwg.rect(insert=(10, 40), size=(100, 20), fill='lightblue'))
    dwg.add(dwg.text('MFC Block Record', insert=(15, 50), font_size=12))

    # Draw the fields
    fields = [
        ('magic', 4),
        ('version', 4),
        ('num_blocks', 4),
        ('block_size', 4),
        ('reserved', 4),
    ]
    y = 70
    for field, size in fields:
        dwg.add(dwg.rect(insert=(10, y), size=(size*10, 20), fill='lightgray'))
        dwg.add(dwg.text(field, insert=(15, y+15), font_size=10))
        y += 25

    fields = [
        ('block_id', 4),
        ('block_size', 4),
        ('data_offset', 4),
        ('data_size', 4),
    ]
    y = 70
    dwg.add(dwg.rect(insert=(150, 40), size=(100, 20), fill='lightblue'))
    dwg.add(dwg.text('MFC Block Record', insert=(155, 50), font_size=12))
    y = 70
    for field, size in fields:
        dwg.add(dwg.rect(insert=(150, y), size=(size*10, 20), fill='lightgray'))
        dwg.add(dwg.text(field, insert=(155, y+15), font_size=10))
        y += 25

    dwg.save()

# Link the diagram in README
def link_diagram_in_readme():
    with open('README.md', 'r') as f:
        lines = f.readlines()

    with open('README.md', 'w') as f:
        for line in lines:
            if line.startswith('## Diagrams'):
                f.write(line)
                f.write('[MFC Container Layout](docs/diagrams/mfc_layout.svg)\n')
            else:
                f.write(line)

create_diagram()
link_diagram_in_readme()