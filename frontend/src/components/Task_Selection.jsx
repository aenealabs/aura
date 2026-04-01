// frontend/src/components/TaskSelection.jsx


// Placeholder icons - we can replace these with actual SVG components later
const AddIcon = () => <span>➕</span>;
const RefactorIcon = () => <span>🔄</span>;
const BugIcon = () => <span>🐞</span>;
const SecurityIcon = () => <span>🛡️</span>;

const tasks = {
  development: [
    {
      id: 'ADD_FEATURE',
      title: 'Add feature',
      description: 'Build new functionality and expand your app\'s capabilities',
      icon: <AddIcon />
    },
    {
      id: 'REFACTOR_CODEBASE',
      title: 'Refactor codebase',
      description: 'Upgrade version, migrate languages, or restructure code base architecture',
      icon: <RefactorIcon />
    },
  ],
  quality: [
    {
      id: 'FIX_BUGS',
      title: 'Fix bugs',
      description: 'Identify and resolve errors, crashes, or unexpected behavior',
      icon: <BugIcon />
    },
    {
      id: 'FIX_SECURITY',
      title: 'Fix security vulnerabilities',
      description: 'Remediate CVEs and strengthen any security gaps',
      icon: <SecurityIcon />
    },
  ],
};

const TaskCard = ({ task, onSelect }) => (
  <div className="task-card" onClick={() => onSelect(task.id)}>
    <div className="task-icon">{task.icon}</div>
    <h3>{task.title}</h3>
    <p>{task.description}</p>
  </div>
);

const TaskSelection = ({ onTaskSelect }) => {
  return (
    <div className="task-selection-container">
      <h2>Development & Modernization</h2>
      <div className="task-grid">
        {tasks.development.map(task => <TaskCard key={task.id} task={task} onSelect={onTaskSelect} />)}
      </div>

      <h2>Quality & Maintenance</h2>
      <div className="task-grid">
        {tasks.quality.map(task => <TaskCard key={task.id} task={task} onSelect={onTaskSelect} />)}
      </div>

      {/* We will add "Testing & Documentation" here later */}
    </div>
  );
};

export default TaskSelection;
