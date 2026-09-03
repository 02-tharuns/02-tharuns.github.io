<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1E1638,35:3B2A6E,72:2BC4B8,100:F5A623&height=200&section=header&text=Tharun%20Subramanya&fontSize=44&fontColor=FFFFFF&animation=fadeIn&fontAlignY=36&desc=Machine%20Learning%20for%20Industrial%20%26%20Automotive%20Systems&descAlignY=56&descSize=16" width="100%"/>

<a href="https://linkedin.com/in/tharun-subramanya-p">
<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=17&pause=1200&color=2BC4B8&center=true&vCenter=true&width=900&height=45&lines=MS+Artificial+Intelligence+%7C+University+of+Michigan-Dearborn;BE+Industrial+and+Production+Engineering;Automotive+Diagnostics+today%2C+Industrial+Robotics+and+IIoT+next" alt="Typing SVG" />
</a>

<br><br>

<img src="https://img.shields.io/badge/Edge%20AI-2BC4B8?style=for-the-badge&logoColor=white" />
<img src="https://img.shields.io/badge/Predictive%20Maintenance-F5A623?style=for-the-badge&logoColor=1E1638" />
<img src="https://img.shields.io/badge/Industrial%20IoT-7C5CE8?style=for-the-badge&logoColor=white" />

</div>

<br>

## Who I am

An **Industrial and Production Engineering** graduate who moved into applied AI. My first degree taught me to think in tolerances, failure modes and throughput. An edge computing course during my Master's turned that into something specific: latency budgets, sensor noise, and inference on constrained hardware. Not AI in the abstract, but **AI that has to survive contact with a physical machine.**

Everything I have shipped since is automotive diagnostics. Brake and wheel end condition monitoring. CAN bus fault classification. Bearing vibration. Buzz, squeak and rattle detection. The question is the same every time: **how do you get a model to tell the truth about a physical system before it fails?**

<br>

## Where I am going

> ### Industrial robotics and IIoT.
> The move is deliberate rather than opportunistic.

Predicting a bearing failure from vibration, telling real drift apart from a benign environmental shift, and holding inference inside a millisecond budget on constrained hardware are not automotive problems. They are **machine health problems**.

A robot joint has a gearbox, a duty cycle and a thermal signature. A plant floor runs the same telemetry backbone as a test vehicle. I already own the sensor to decision half of that. What I am building now is the manipulator and plant floor half.

<br>

## What I am working toward

| | Goal | How I am getting there |
|:--:|---|---|
| ![](https://img.shields.io/badge/01-2BC4B8?style=flat-square) | Joint level health monitoring for manipulators | Applying the brake and bearing diagnostics stack to gearbox and actuator signals |
| ![](https://img.shields.io/badge/02-F5A623?style=flat-square) | Fluency in the industrial robotics stack | Manipulator kinematics, ROS 2, and the vocabulary of plant floor integration |
| ![](https://img.shields.io/badge/03-7C5CE8?style=flat-square) | Deployment I can defend, not just demo | CI gated test suites, held out evaluation, and honest reported numbers |
| ![](https://img.shields.io/badge/04-2BC4B8?style=flat-square) | Stronger data engineering | Closing a flagged SQL gap and pushing further into ETL and Spark |

<br>

## What I am building right now

<table>
<tr>
<td width="50%" valign="top">

### ![](https://img.shields.io/badge/-2BC4B8?style=flat-square) Smart Brake and Wheel End Monitor

Physics first brake diagnostics, built with a collaborator. My half: a lumped capacitance rotor thermal simulator with speed dependent convection and radiation, residual caliper drag torque injection across four severity levels, and a Newtonian cooling curve extractor that **inverts torque from the cooling asymptote**, landing within **~5% of ground truth** on severe drag cases.

Physical inversion over black box classification, deliberately. An interpretable torque estimate tells a service engineer a diagnostic story that a confidence score cannot.

`18 test suite` `ruff` `pytest` `coverage` `CI gated`

</td>
<td width="50%" valign="top">

### ![](https://img.shields.io/badge/-F5A623?style=flat-square) DARE-PM

*Drift Aware, Event Triggered Edge Predictive Maintenance*

14 time and frequency domain features every 0.1 s from vibration and acoustic streams, on device. One-Class SVM novelty detection with ADWIN drift diagnosis cut **false adaptations from 49.87% to under 1%** at F1 up to 0.80, reaching **88.4% data reduction and 3.8 ms inference** across 48 controlled experiments.

Reframed under faculty mentorship toward vehicle BSR detection. The open problem: ADWIN alone cannot tell a real fault from a benign environmental shift, so I am building a multi signal arbitration layer.

`One-Class SVM` `ADWIN` `MQTT` `Docker` `InfluxDB` `Grafana`

</td>
</tr>
</table>

<br>

## How I work

> I default to the next concrete step, not open ended reflection. Milestones over meandering.
>
> I run several learning tracks in parallel rather than sequencing them.
>
> I build domain fluency alongside implementation. You cannot model brake drag torque well without understanding what a caliper is actually doing.
>
> When a research direction hits literature saturation, that is a signal to pivot early, not a reason to force it.

<br>

## Lessons from the trenches

<details open>
<summary><b>A running log of things that broke and taught me something</b></summary>

<br>

- **ADWIN alone cannot separate true concept drift from benign environmental shift.** You need a second signal to arbitrate. This one reshaped an entire project.
- **Physical inversion beats black box classification for credibility.** An interpretable torque estimate from a cooling curve tells a diagnostic story that a classifier score cannot.
- **A random split leaks on video data.** Consecutive frames of one vehicle land on both sides of the boundary. A group level split by video reports a lower number that is actually true.
- **Validate each layer independently before end to end testing.** Sensor, broker, subscriber, storage, alert. Skip to the full pipeline and you will spend twice as long finding which link broke.
- **AWS region mismatches** between IoT Core, Lambda and SES fail silently. Match regions across every service, not only the ones you touched last.
- **Certificate filename mismatches** in IoT auth scripts are the classic "it worked yesterday" bug. Name things explicitly.
- **Unit conversion bugs are sneakier than they look.** A Celsius to Fahrenheit error that always trips your threshold passes every casual test and fails in production.

</details>

<br>

## Projects worth a look

| | Project | What it does |
|:--:|---|---|
| ![](https://img.shields.io/badge/-2BC4B8?style=flat-square) | **Smart Brake and Wheel End Monitor** | Rotor thermal simulation, drag torque injection, cooling curve torque inversion within ~5% |
| ![](https://img.shields.io/badge/-F5A623?style=flat-square) | **DARE-PM** | Drift aware edge predictive maintenance. One-Class SVM with ADWIN, false adaptations 49.87% to under 1%, 3.8 ms inference |
| ![](https://img.shields.io/badge/-2BC4B8?style=flat-square) | **CANalyse Edge** | CAN and CAN-FD decoding into named signals via DBC, Random Forest condition model, SOVD inspired FastAPI diagnostic service |
| ![](https://img.shields.io/badge/-F5A623?style=flat-square) | **Edge Sensing and Digital Twin** | Raspberry Pi with Mosquitto MQTT to a Python subscriber, extended to AWS IoT Core, Lambda and SES on real hardware |
| ![](https://img.shields.io/badge/-7C5CE8?style=flat-square) | **Supply Chain Risk Pipeline** | Late delivery prediction over 180K orders. One hot dimensionality cut from 64K features to 339, recall raised 57.5% to 78.8% |
| ![](https://img.shields.io/badge/-7C5CE8?style=flat-square) | **Chappie** | Retrieval chatbot over my own documents, running entirely in browser. BM25, six guardrails, extractive answers, 69 case eval suite in CI |

<br>

## Tech I reach for

**Core**

![Python](https://img.shields.io/badge/Python-2BC4B8?style=for-the-badge&logo=python&logoColor=white)
![SQL](https://img.shields.io/badge/SQL-2BC4B8?style=for-the-badge&logo=postgresql&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2BC4B8?style=for-the-badge&logo=numpy&logoColor=white)
![Pandas](https://img.shields.io/badge/Pandas-2BC4B8?style=for-the-badge&logo=pandas&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-2BC4B8?style=for-the-badge&logo=scikitlearn&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2BC4B8?style=for-the-badge&logo=pytorch&logoColor=white)
![TensorFlow](https://img.shields.io/badge/TensorFlow-2BC4B8?style=for-the-badge&logo=tensorflow&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-2BC4B8?style=for-the-badge&logo=opencv&logoColor=white)

**Edge and IIoT**

![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi%205-F5A623?style=for-the-badge&logo=raspberrypi&logoColor=1E1638)
![MQTT](https://img.shields.io/badge/MQTT%20%2F%20Mosquitto-F5A623?style=for-the-badge&logo=mqtt&logoColor=1E1638)
![AWS IoT](https://img.shields.io/badge/AWS%20IoT%20Core-F5A623?style=for-the-badge&logo=amazonaws&logoColor=1E1638)
![InfluxDB](https://img.shields.io/badge/InfluxDB-F5A623?style=for-the-badge&logo=influxdb&logoColor=1E1638)
![Grafana](https://img.shields.io/badge/Grafana-F5A623?style=for-the-badge&logo=grafana&logoColor=1E1638)

**Ship it**

![Docker](https://img.shields.io/badge/Docker-7C5CE8?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-7C5CE8?style=for-the-badge&logo=linux&logoColor=white)
![Git](https://img.shields.io/badge/Git-7C5CE8?style=for-the-badge&logo=git&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-7C5CE8?style=for-the-badge&logo=githubactions&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-7C5CE8?style=for-the-badge&logo=fastapi&logoColor=white)
![pytest](https://img.shields.io/badge/pytest-7C5CE8?style=for-the-badge&logo=pytest&logoColor=white)

**Also used** · Spark and PySpark · Airflow · Azure · XGBoost · Hugging Face · LangChain · Power BI · Tableau · Plotly · R

<br>

## Most importantly

Debugging, implementation, documentation and editing. That is the job most days. Not the demo, the ten hours before it.

<br>

<div align="center">

## Let's connect

Automotive diagnostics, industrial robotics, edge AI, or anything with a gearbox and a duty cycle.

[![Gmail](https://img.shields.io/badge/tharunmysuru%40gmail.com-F5A623?style=for-the-badge&logo=gmail&logoColor=1E1638)](mailto:tharunmysuru@gmail.com)
[![LinkedIn](https://img.shields.io/badge/tharun--subramanya--p-2BC4B8?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/tharun-subramanya-p)

<br>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:F5A623,30:2BC4B8,68:3B2A6E,100:1E1638&height=110&section=footer" width="100%"/>

</div>
