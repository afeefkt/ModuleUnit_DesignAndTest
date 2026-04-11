/* Generated from: RE_ProcessEPS Code Flow */
/* Requirements: EPS-001, EPS-002, EPS-003, EPS-004 */
/* Model: qwen2.5-coder:7b, confidence: 0.65 */

#include "Rte_Type.h"
#include "Rte_SWC_ElectricPowerSteering.h"

static void EPS_CalcAssistTorque(void);  /* see sub-diagram */

/* Local variables */
static float32 l_f32AssistTorque;
static float32 l_f32Speed;
static float32 l_f32Torque;

void RE_ProcessEPS(void)
{
    /* [EPS-002] */
    Rte_Read_RP_VehicleSpeed_Speed(&l_f32Speed);
    /* [EPS-002] */
    Rte_Read_RP_SteeringTorque_Torque(&l_f32Torque);
    /* [EPS-003] */
    if (if (l_f32Speed > MAX_SPEED_KMH || steering_fault_detected) { l_f32AssistTorque = 0; raise_DEM_event(); })
    {
        /* [EPS-004] */
        Rte_Write_PP_AssistTorque_Torque(l_f32AssistTorque);
        return; /* [EPS-001] */
    }
    else
    {
    }
}


/* Generated from: EPS_CalcAssistTorque Code Flow */
/* Requirements: EPS-005 */
/* Model: qwen2.5-coder:7b, confidence: 0.65 */

#include "Rte_Type.h"
#include "Rte_SWC_ElectricPowerSteering.h"

/* Local variables */
static float32 l_f32Speed;
static float32 l_f32Torque;

void EPS_CalcAssistTorque(void)
{
    /* [EPS-005] */
    l_f32Torque = l_f32Speed * GAIN_FACTOR + l_f32Torque * BOOST_FACTOR;
    return; /* [EPS-005] */
}
