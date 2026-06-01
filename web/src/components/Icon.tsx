import { 
  AccountCircle, 
  Settings, 
  History, 
  Science, 
  Description, 
  CheckCircle, 
  Close, 
  HelpCircle, 
  Info, 
  MenuBook, 
  Bell, 
  Printer, 
  Activity, 
  AlertTriangle, 
  Search, 
  SwapHorizontal, 
  Timer, 
  ShieldCheck, 
  LucideProps 
} from 'lucide-react';

const ICON_MAP: Record<string, React.ElementType> = {
  account_circle: AccountCircle,
  settings: Settings,
  history: History,
  science: Science,
  description: Description,
  check_circle: CheckCircle,
  close: Close,
  help: HelpCircle,
  info: Info,
  menu_book: MenuBook,
  notifications: Bell,
  print: Printer,
  progress_activity: Activity,
  report_problem: AlertTriangle,
  search: Search,
  swap_horiz: SwapHorizontal,
  timer: Timer,
  verified_user: ShieldCheck,
  warning: AlertTriangle,
};

type IconProps = LucideProps & {
  name: string;
};

export default function Icon({ name, ...props }: IconProps) {
  const LucideIcon = ICON_MAP[name] ?? Info;
  return <LucideIcon {...props} />;
}
