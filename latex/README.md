# LaTeX documents

This folder contains three LaTeX source documents and their compiled PDFs:

| PDF | LaTeX source | Contents |
|---|---|---|
| `pdf/Source_Code_Documentation.pdf` | `src/source_code_documentation.tex` | Repository map, script and SQL responsibilities, data flow, definitions, and reproduction commands. |
| `pdf/Technical_Project_Report.pdf` | `src/technical_report.tex` | Project objective, data, methods, results, limitations, audit findings, and a Q&A section at the end. |
| `pdf/PowerBI_Implementation_Guide.pdf` | `src/powerbi_implementation_guide.tex` | Step-by-step instructions to import the prepared Power BI package, build the model/report pages, and reconcile a native report. |

Shared LaTeX styling is in `src/common.tex`. Recompile all three PDFs from the repository root with XeLaTeX:

```sh
sh latex/compile.sh
```

Intermediate `.aux`, `.log`, `.toc`, and other build files are kept in `build/`; only the three deliverable PDFs are in `pdf/`. The Power BI guide's import, relationship, and date-table instructions were checked against Microsoft Learn on 31 October 2026; official links are included in the TeX source and PDF. The guide describes a handoff only: there is still no native Power BI `.pbix` in this repository.
