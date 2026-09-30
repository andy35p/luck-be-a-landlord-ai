using SlotWeave;
using SlotWeave.Modding;
using System.Reflection;

namespace LandlordResearch;

public sealed class Mod : IMod
{
    public Mod(IModInterface api) => api.RegisterSourceMod(new CollectorSource());
    public void Dispose() { }
}

public sealed class CollectorSource : ISourceMod
{
    public bool ShouldRun(string path) => path is "res://Main.tscn::1" or "res://Pop-up.tscn::1";

    public string Modify(string path, string source)
    {
        if (source.Contains("# LANDLORD_RESEARCH_V1")) return source;
        source = source.Replace("\r\n", "\n");
        if (path == "res://Main.tscn::1")
        {
            const string anchor = "func _process(delta):\n";
            if (source.Split(anchor).Length != 2) throw new InvalidOperationException("Main process anchor mismatch");
            source = source.Replace(anchor, anchor + "\t_lr_tick(delta)\n");
            using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("LandlordResearch.collector.gd")!;
            return source + "\n" + new StreamReader(stream).ReadToEnd();
        }
        const string resolve = "func resolve_event(choice):\n";
        const string cards = "func add_cards(f_rarities):\n";
        if (source.Split(cards).Length != 2) throw new InvalidOperationException("Test card anchor mismatch");
        source = source.Replace(cards, cards + "\t# CONTROLLED_CHOICE_TEST_ONLY\n\tif current_floor == 1 and emails.size() > 0 and emails[0].type == \"add_tile\":\n\t\tsaved_card_types = [\"cheese\", \"coin\", \"flower\"] if spins == 1 else [\"mouse\", \"milk\", \"flower\"]\n");
        if (source.Split(resolve).Length != 2) throw new InvalidOperationException("Resolve anchor mismatch");
        return source.Replace(resolve, resolve + "\t# LANDLORD_RESEARCH_V1\n\tvar lr_main = get_node_or_null(\"/root/Main\")\n\tif lr_main != null and lr_main.has_method(\"_lr_capture\"):\n\t\tlr_main._lr_capture(\"action_attempt\", choice)\n");
    }
}
