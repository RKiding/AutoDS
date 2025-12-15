"""
Report Agent: Responsible for generating structured final reports based on task context.
Dynamically selects the appropriate report guide based on project history and execution context.
"""

from typing import Optional
from agno.agent import Agent
from src.schema.models import Context


class ReportAgent:
    """
    Generates comprehensive final reports by analyzing the project context and selecting
    the most appropriate report structure (guide) dynamically.
    """

    def __init__(self):
        pass

    @staticmethod
    def get_task_type_guide_prompt(project_history: str) -> str:
        """
        First-pass prompt: Analyze the project history and determine the task type.
        This is more comprehensive than keyword matching.
        """
        return f"""
You are a Project Type Analyzer. Analyze the following project execution history and determine the type of task that was performed.

Project Execution History:
{project_history}

Based on the execution history, identify the primary task type from these categories:

1. **Modeling**: The project involves training machine learning models, predictions, classification, regression, neural networks, etc. Focus on model development, training, evaluation, and performance metrics.

2. **Analysis**: The project involves exploratory data analysis, generating insights, finding patterns, trends, correlations, statistical analysis. Focus on discoveries and findings from data.

3. **Data Processing**: The project involves data cleaning, preprocessing, transformation, aggregation, merging, formatting, schema changes. Focus on data pipeline and quality.

4. **Implementation**: The project involves building, creating, writing, developing, implementing software components, APIs, scripts, extracting features. Focus on code development and architecture.

5. **General**: The project doesn't fit neatly into above categories or is a mix of multiple types.

Analyze the execution history carefully:
- What were the main operations performed?
- What tools/agents were used most?
- What was the final output?
- What was the focus (model? data? insights? code?)?

Output ONLY the task type name from the categories above (e.g., "Modeling", "Analysis", "Data Processing", "Implementation", or "General").
Do not include any explanation, just the category name.
"""

    @staticmethod
    def get_modeling_report_guide() -> str:
        """Guide template for modeling/ML projects."""
        return """
## 1. Executive Summary
- Brief overview of the modeling objective and approach

## 2. Data Understanding & Preparation
- Data sources and characteristics
- Data preprocessing steps performed
- Feature engineering details (if any)
- Train/test split and data quality issues addressed

## 3. Modeling Approach
- Models trained and algorithms used
- Hyperparameter configurations
- Cross-validation strategy (if used)
- Rationale for model selection

## 4. Model Performance & Evaluation
- Key performance metrics (accuracy, precision, recall, F1, AUC, RMSE, etc.)
- Performance comparison between models
- Confusion matrix or error analysis (if applicable)
- Validation results

## 5. Key Findings & Insights
- Most important features/patterns discovered
- Model behavior and limitations
- Recommendations for improvement

## 6. Deliverables
- Final model files and their locations
- Output files (predictions, submission files, etc.)
- Code artifacts and notebooks

## 7. Next Steps & Future Work
- Potential improvements
- Deployment considerations
- Additional experiments to try
"""

    @staticmethod
    def get_analysis_report_guide() -> str:
        """Guide template for analysis/EDA projects."""
        return """
## 1. Objective & Scope
- What was being analyzed
- Key questions addressed
- Data sources used

## 2. Data Overview
- Dataset characteristics (size, features, data types)
- Data quality and missing values
- Basic statistical summary

## 3. Exploratory Data Analysis (EDA)
- Key distributions and patterns
- Univariate analysis highlights
- Relationships and correlations discovered
- Outliers or anomalies identified

## 4. Key Insights & Findings
- Main discoveries organized by topic
- Statistical findings and their significance
- Business implications
- Notable patterns or anomalies

## 5. Visualizations & Evidence
- Summary of key charts/plots generated
- Supporting evidence for main findings
- Data quality or data issues found

## 6. Recommendations
- Actionable insights for decision-making
- Areas requiring further investigation
- Data collection or improvement suggestions

## 7. Output Files & Artifacts
- Generated charts, plots, and reports
- Data extracts or exports created
- Code and notebooks used
"""

    @staticmethod
    def get_data_processing_report_guide() -> str:
        """Guide template for data processing/engineering projects."""
        return """
## 1. Processing Objective
- Goal of the data processing pipeline
- Input data sources and formats
- Output requirements and formats

## 2. Data Quality Assessment
- Initial data quality issues
- Missing values, duplicates, inconsistencies found
- Data types and schema validation

## 3. Processing Steps Executed
- Data cleaning operations performed
- Transformation and normalization steps
- Aggregation and grouping operations
- Feature engineering or derived field creation

## 4. Data Validation & Verification
- Quality checks performed post-processing
- Row/record count verification
- Schema validation results
- Sample outputs for verification

## 5. Performance Metrics
- Processing time and efficiency
- Data volume processed (rows, file size)
- Error rates or data loss (if any)
- Resource utilization

## 6. Output Specifications
- Final data format and structure
- File locations and naming conventions
- Record count and completeness verification
- Sample of processed data

## 7. Documentation & Reusability
- Process documentation for future runs
- Parameters that can be modified
- Dependencies and requirements
- Recommended next steps
"""

    @staticmethod
    def get_implementation_report_guide() -> str:
        """Guide template for implementation/development projects."""
        return """
## 1. Project Overview
- Implementation objective and scope
- Requirements and success criteria
- Technology stack and tools used

## 2. Implementation Approach
- Architecture and design decisions
- Major components and modules built
- Third-party libraries or services utilized
- Key algorithms or logic implemented

## 3. Development Progress
- Features implemented
- Functionality completed vs. planned
- Challenges encountered and resolutions
- Code quality and best practices applied

## 4. Testing & Verification
- Testing strategy and coverage
- Test results and validation
- Known issues or limitations
- Edge cases handled

## 5. Code & Technical Artifacts
- Main code files and their purpose
- Configuration files and settings
- API endpoints or functions exposed
- Dependencies and requirements

## 6. Performance & Optimization
- Performance characteristics and benchmarks
- Optimization techniques applied
- Scalability considerations
- Resource usage

## 7. Documentation & Deployment
- Code documentation and comments
- Usage instructions and examples
- Deployment process and prerequisites
- Future maintenance and upgrades

## 8. Deliverables Summary
- All output files and artifacts
- Installation and setup instructions
- Testing procedures for end users
"""

    @staticmethod
    def get_general_report_guide() -> str:
        """Guide template for general/mixed projects."""
        return """
## 1. Project Summary
- What was the main objective?
- What approach was taken?
- Overall assessment of success

## 2. What Was Accomplished
- Main achievements and completed items
- Key outputs and deliverables
- Metrics or measurable results (if any)

## 3. Process & Methodology
- Steps taken to achieve the goal
- Tools and techniques used
- Time and resource considerations

## 4. Findings & Insights
- Key discoveries or learnings
- Unexpected outcomes
- Notable patterns or relationships found

## 5. Challenges & Solutions
- Problems encountered
- How they were resolved
- Lessons learned

## 6. Output Files & Artifacts
- All generated files and their purposes
- Locations and how to access them
- File formats and specifications

## 7. Recommendations & Next Steps
- Suggested improvements or enhancements
- Future work or iterations
- Areas for further exploration

## 8. Conclusion
- Overall summary of the project
- Value delivered
- Final status and sign-off
"""

    @staticmethod
    def select_report_guide(task_type: str) -> str:
        """Select the appropriate report guide based on task type."""
        guides = {
            "Modeling": ReportAgent.get_modeling_report_guide(),
            "Analysis": ReportAgent.get_analysis_report_guide(),
            "Data Processing": ReportAgent.get_data_processing_report_guide(),
            "Implementation": ReportAgent.get_implementation_report_guide(),
        }
        return guides.get(task_type, ReportAgent.get_general_report_guide())

    @staticmethod
    def generate_final_report(
        user_goal: str,
        project_history: str,
        model,
        logger_callback=None
    ) -> tuple[str, str]:
        """
        Generate a comprehensive final report with intelligent task type detection.
        
        Args:
            user_goal: Original user goal
            project_history: Project execution history
            model: LLM model to use for report generation
            logger_callback: Optional callback for logging
            
        Returns:
            Tuple of (task_type, report_content)
        """
        if logger_callback is None:
            logger_callback = print

        # Step 1: Determine task type from project context
        logger_callback("   🔍 Analyzing project context to determine task type...")
        
        type_detection_prompt = ReportAgent.get_task_type_guide_prompt(project_history)
        
        try:
            type_agent = Agent(
                model=model,
                instructions=["You are a project type analyzer. Respond with only the task type name."],
                markdown=False
            )
            type_response = type_agent.run(type_detection_prompt)
            task_type = type_response.content.strip()
            
            # Validate the response
            valid_types = ["Modeling", "Analysis", "Data Processing", "Implementation", "General"]
            if task_type not in valid_types:
                logger_callback(f"   ⚠️ Detected task type '{task_type}' not recognized. Using 'General'.")
                task_type = "General"
            else:
                logger_callback(f"   ✅ Task Type Detected: {task_type}")
                
        except Exception as e:
            logger_callback(f"   ⚠️ Error detecting task type: {e}. Using 'General'.")
            task_type = "General"

        # Step 2: Generate report with appropriate guide
        logger_callback(f"   📝 Generating {task_type} Report...")
        
        report_guide = ReportAgent.select_report_guide(task_type)
        
        report_prompt = f"""
You are a professional {task_type} Report Generator.

User Goal: {user_goal}

Project Execution History:
{project_history}

Please generate a comprehensive {task_type} Report following this structure:

{report_guide}

Guidelines:
- Be specific and data-driven where applicable
- Use metrics, numbers, and quantifiable results
- Include relevant details from the execution history
- Keep sections concise but informative
- Highlight key achievements and outcomes
"""

        try:
            report_agent = Agent(
                name=f"{task_type}ReportAgent",
                model=model,
                instructions=[f"You are a professional {task_type} report writer. Generate clear, structured reports."],
                markdown=True
            )
            report_response = report_agent.run(report_prompt)
            report_content = report_response.content
            
            return task_type, report_content
            
        except Exception as e:
            logger_callback(f"   ❌ Failed to generate report: {e}")
            return task_type, f"Error generating report: {e}"
