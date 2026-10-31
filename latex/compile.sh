#!/bin/sh
set -eu
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$script_dir/src"
mkdir -p ../build ../pdf
for source in source_code_documentation.tex technical_report.tex powerbi_implementation_guide.tex; do
  xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=../build "$source"
  xelatex -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=../build "$source"
done
cp ../build/source_code_documentation.pdf ../pdf/Source_Code_Documentation.pdf
cp ../build/technical_report.pdf ../pdf/Technical_Project_Report.pdf
cp ../build/powerbi_implementation_guide.pdf ../pdf/PowerBI_Implementation_Guide.pdf
