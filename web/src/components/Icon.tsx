import { 
  UserCircle, 
  Settings, 
  History, 
  FlaskConical, 
  FileText, 
  CheckCircle, 
  X, 
  HelpCircle, 
  Info, 
  BookOpen, 
  Bell, 
  Printer, 
  Loader2, 
  AlertTriangle, 
  Search, 
  ArrowRightLeft, 
  Timer, 
  ShieldCheck, 
  Dna,
  Mail,
  Lock,
  AlertCircle,
  LogIn,
  User,
  Shield,
  Check,
  ChevronDown,
  LineChart,
  Lightbulb,
  ClipboardList,
  Pill,
  type LucideProps 
} from 'lucide-react';

const ICON_MAP: Record<string, React.ElementType> = {
  account_circle: UserCircle,
  settings: Settings,
  history: History,
  science: FlaskConical,
  description: FileText,
  check_circle: CheckCircle,
  close: X,
  help: HelpCircle,
  info: Info,
  menu_book: BookOpen,
  notifications: Bell,
  print: Printer,
  progress_activity: Loader2,
  report_problem: AlertTriangle,
  search: Search,
  swap_horiz: ArrowRightLeft,
  timer: Timer,
  verified_user: ShieldCheck,
  warning: AlertTriangle,
  biotech: Dna,
  mail: Mail,
  lock: Lock,
  error: AlertCircle,
  login: LogIn,
  person: User,
  security: Shield,
  check: Check,
  expand_more: ChevronDown,
  analytics: LineChart,
  insights: Lightbulb,
  assignment_ind: ClipboardList,
  medication: Pill,
};

type IconProps = LucideProps & {
  name: string;
};

export default function Icon({ name, ...props }: IconProps) {
  const LucideIcon = ICON_MAP[name] ?? Info;
  return <LucideIcon {...props} />;
}
