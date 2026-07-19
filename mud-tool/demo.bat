@echo off
REM ============================================================
REM  MUD Tool - Quick Demo (no API key needed)
REM  Tests import, validation, and export locally
REM ============================================================
setlocal

cd /d "%~dp0python-sidecar"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found. Run setup.bat first!
    pause
    exit /b 1
)

echo.
echo ================================================================
echo  MUD Tool - Quick Demo (offline, no API key needed)
echo ================================================================
echo.

python -c "
import sys, json
from pathlib import Path

# ── Step 1: Import Requirements ──
print('='*60)
print(' STEP 1: Importing requirements from sample file')
print('='*60)
from mudtool.importers.factory import ImporterFactory

result = ImporterFactory.import_file(Path('../data/sample/sample_requirements.csv'))
print(f'  Imported: {result.requirement_set.count} requirements')
print(f'  Format:   {result.requirement_set.source_format}')
print(f'  Warnings: {len(result.warnings)}')
print(f'  Success:  {result.success}')
print()
for req in result.requirement_set.requirements[:5]:
    print(f'  [{req.req_id}] {req.title}')
    print(f'    Type: {req.req_type.value} | Priority: {req.priority.value} | ASIL: {req.safety_level}')
print(f'  ... and {result.requirement_set.count - 5} more')
print()

# ── Step 2: Also test TXT import ──
print('='*60)
print(' STEP 2: Importing from TXT format')
print('='*60)
result2 = ImporterFactory.import_file(Path('../data/sample/sample_requirements.txt'))
print(f'  Imported: {result2.requirement_set.count} requirements from TXT')
print()

# ── Step 3: Create a mock diagram and validate ──
print('='*60)
print(' STEP 3: Validating a sample AUTOSAR model')
print('='*60)

from mudtool.config.settings import Settings
from mudtool.models.json_uml import *
from mudtool.validation.engine import ValidationEngine

settings = Settings()
validator = ValidationEngine(settings)

# Build a sample diagram set
seq = SequenceDiagram(
    name='SensorFusion_DataFlow',
    source_requirements=['REQ-ARCH-0100', 'REQ-ARCH-0201'],
    lifelines=[
        Lifeline(id='ll_1', name='SWC_SensorFusion', type='ApplicationSWC',
                 runnable='RE_FuseSensorData', trace_reqs=['REQ-ARCH-0100']),
        Lifeline(id='ll_2', name='SWC_VehicleControl', type='ApplicationSWC',
                 runnable='RE_ProcessData', trace_reqs=['REQ-ARCH-0201']),
    ],
    messages=[
        Message(id='m1', **{'from': 'll_1', 'to': 'll_2'},
                rte_call='Rte_Write', port='PP_FusedData',
                element='DE_FusedEnvironmentModel',
                trace_req='REQ-ARCH-0100', confidence=0.92),
    ],
    provenance=Provenance(ai_model='demo', prompt_version='demo-v1', confidence=0.9),
)

sm = StateMachineDiagram(
    name='SensorFusion_Lifecycle',
    owner_swc='SWC_SensorFusion',
    source_requirements=['REQ-ARCH-0104'],
    states=[
        State(id='s0', name='INITIAL', is_initial=True),
        State(id='s1', name='INIT', trace_reqs=['REQ-ARCH-0104']),
        State(id='s2', name='RUNNING', trace_reqs=['REQ-ARCH-0104']),
        State(id='s3', name='DEGRADED', trace_reqs=['REQ-ARCH-0103']),
        State(id='s4', name='SHUTDOWN', trace_reqs=['REQ-ARCH-0104']),
    ],
    transitions=[
        Transition(id='t1', source='s0', target='s1', trigger='PowerOn'),
        Transition(id='t2', source='s1', target='s2', trigger='InitComplete'),
        Transition(id='t3', source='s2', target='s3', trigger='SensorFailure'),
        Transition(id='t4', source='s3', target='s2', trigger='Recovery'),
        Transition(id='t5', source='s2', target='s4', trigger='Shutdown'),
    ],
    provenance=Provenance(ai_model='demo', prompt_version='demo-v1', confidence=0.88),
)

cls_diag = ClassDiagram(
    name='SensorFusion_Design',
    source_requirements=['REQ-ARCH-0100', 'REQ-ARCH-0101'],
    classes=[
        ClassElement(
            id='c1', name='SWC_SensorFusion', stereotype='ApplicationSWC',
            operations=[
                ClassOperation(name='RE_InitFusion', trigger_type='init',
                               trace_reqs=['REQ-ARCH-0100']),
                ClassOperation(name='RE_FuseSensorData', trigger_type='cyclic',
                               period_ms=10.0, trace_reqs=['REQ-ARCH-0101']),
            ],
            trace_reqs=['REQ-ARCH-0100', 'REQ-ARCH-0101'],
        ),
    ],
    provenance=Provenance(ai_model='demo', prompt_version='demo-v1', confidence=0.91),
)

gen_result = GenerationResult(diagrams=[seq, sm, cls_diag])

req_ids = [r.req_id for r in result.requirement_set.requirements]
report = validator.validate(gen_result, requirement_ids=req_ids)
print(f'  {report.summary()}')
print()
for issue in report.issues[:10]:
    icon = {'error': 'X', 'warning': '!', 'info': 'i'}[issue.severity.value]
    print(f'  [{icon}] {issue.rule_id} ({issue.category}): {issue.message[:80]}')
if len(report.issues) > 10:
    print(f'  ... and {len(report.issues) - 10} more issues')
print()

# ── Step 4: Export to PlantUML ──
print('='*60)
print(' STEP 4: Exporting to PlantUML')
print('='*60)

from mudtool.generator.plantuml_exporter import PlantUMLExporter

exporter = PlantUMLExporter()
output_dir = Path('../output/demo')
paths = exporter.export_result(gen_result, output_dir)
print(f'  Exported {len(paths)} PlantUML files:')
for p in paths:
    print(f'    {p.name}')
print()

# ── Step 5: Export to XMI ──
print('='*60)
print(' STEP 5: Exporting to XMI (UML 2.x)')
print('='*60)

from mudtool.generator.xmi_exporter import XMIExporter

xmi_exporter = XMIExporter()
xmi_path = Path('../output/demo/MUD_Demo_Model.xmi')
xmi_exporter.export_result(gen_result, xmi_path, 'ADAS_SensorFusion')
print(f'  Exported: {xmi_path.name} ({xmi_path.stat().st_size} bytes)')
print()

# ── Step 6: Traceability ──
print('='*60)
print(' STEP 6: Storing traceability links')
print('='*60)

from mudtool.traceability.store import TraceabilityStore
store = TraceabilityStore(settings)
store.initialize()
count = store.extract_and_store_traces(gen_result)
print(f'  Stored {count} trace links')

coverage = store.get_coverage_report(req_ids)
print(f'  Coverage: {coverage[\"coverage_percentage\"]}%% ({coverage[\"covered_requirements\"]}/{coverage[\"total_requirements\"]} requirements)')
if coverage['uncovered_ids']:
    print(f'  Uncovered: {coverage[\"uncovered_ids\"][:5]}')
store.close()

print()
print('='*60)
print(' DEMO COMPLETE!')
print('='*60)
print()
print('  Output files are in: output/demo/')
print('  Open the .puml files in any PlantUML viewer')
print('  Open the .xmi file in Modelio, Papyrus, or Enterprise Architect')
print()
print('  To use AI generation, add your API key to python-sidecar/.env')
print('  Then run: run.bat')
print()
"

pause
