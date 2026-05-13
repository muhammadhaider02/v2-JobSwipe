import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface FormFieldProps {
  label: string;
  id: string;
  error?: string;
  type?: string;
  placeholder?: string;
  required?: boolean;
  value: string;
  onChange: (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => void;
  multiline?: boolean;
  className?: string;
}

export function FormField({
  label,
  id,
  error,
  type = 'text',
  placeholder,
  required,
  value,
  onChange,
  multiline,
  className,
}: FormFieldProps) {
  const Comp = multiline ? Textarea : Input;

  return (
    <div className={cn('grid gap-2', className)}>
      <Label htmlFor={id}>
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      <Comp
        id={id}
        type={multiline ? undefined : type}
        placeholder={placeholder}
        required={required}
        value={value}
        onChange={onChange}
        className={cn(error && 'border-destructive')}
      />
      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
